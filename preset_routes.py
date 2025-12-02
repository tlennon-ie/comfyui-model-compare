"""
API Routes for Grid Preset Analysis

Provides endpoints for analyzing model compare configurations
without running the full generation pipeline.
"""

import json

# Lazy imports - these are only available within ComfyUI context
aiohttp_web = None
PromptServer = None


def register_preset_routes():
    """Register API routes for preset analysis."""
    global aiohttp_web, PromptServer
    
    # Import ComfyUI dependencies only when registering routes
    from aiohttp import web as aiohttp_web
    from server import PromptServer
    
    from .grid_preset_analyzer import (
        analyze_variations,
        generate_optimal_layout,
        get_field_options_for_dropdown,
        validate_layout,
        LayoutRecommendation,
    )
    
    @PromptServer.instance.routes.post("/model_compare/analyze_config")
    async def analyze_config_handler(request):
        """
        Analyze a MODEL_COMPARE_CONFIG to determine optimal grid layout.
        
        Request body:
        {
            "config": { ... },  // MODEL_COMPARE_CONFIG data
            "max_per_grid": 500  // Optional: max images per grid
        }
        
        Response:
        {
            "success": true,
            "analysis": {
                "fields": { field_name: { values, count, is_numeric, ... }, ... },
                "total_combinations": 128,
            },
            "layout": {
                "x_axis": "lora_strength",
                "y_axis": "scheduler",
                "nest_levels": ["prompt", "sampler_name"],
                "num_grids": 1,
                "images_per_grid": 128,
                "preview_text": "...",
                "field_options": ["prompt", "sampler_name", ...],
            },
            "warnings": ["..."]
        }
        """
        try:
            data = await request.json()
            config = data.get('config', {})
            max_per_grid = data.get('max_per_grid', 500)
            
            if not config:
                return aiohttp_web.json_response({
                    "success": False,
                    "error": "No config provided"
                }, status=400)
            
            # Analyze variations
            analysis = analyze_variations(config)
            
            if not analysis:
                return aiohttp_web.json_response({
                    "success": True,
                    "analysis": {
                        "fields": {},
                        "total_combinations": len(config.get('combinations', [])) or 1,
                    },
                    "layout": {
                        "x_axis": None,
                        "y_axis": None,
                        "nest_levels": [],
                        "num_grids": 1,
                        "images_per_grid": len(config.get('combinations', [])) or 1,
                        "preview_text": "No varying dimensions detected - static configuration",
                        "field_options": [],
                    },
                    "warnings": []
                })
            
            # Generate optimal layout
            layout = generate_optimal_layout(analysis, max_per_grid, config)
            
            # Get field options for dropdowns
            field_options = get_field_options_for_dropdown(analysis)
            
            # Validate and get warnings
            warnings = validate_layout(layout, analysis)
            
            # Serialize analysis
            analysis_dict = {}
            for field_name, field_analysis in analysis.items():
                analysis_dict[field_name] = {
                    "display_name": field_analysis.display_name,
                    "values": [str(v) for v in field_analysis.values],
                    "value_count": field_analysis.value_count,
                    "priority": field_analysis.priority,
                    "is_numeric": field_analysis.is_numeric,
                    "is_x_axis_candidate": field_analysis.is_x_axis_candidate,
                    "is_y_axis_candidate": field_analysis.is_y_axis_candidate,
                    "is_nest_candidate": field_analysis.is_nest_candidate,
                }
            
            return aiohttp_web.json_response({
                "success": True,
                "analysis": {
                    "fields": analysis_dict,
                    "total_combinations": layout.total_combinations,
                    "summary": layout.analysis_summary,
                },
                "layout": {
                    "x_axis": layout.x_axis,
                    "y_axis": layout.y_axis,
                    "nest_levels": layout.nest_levels,
                    "num_grids": layout.num_grids,
                    "images_per_grid": layout.images_per_grid,
                    "grid_split_field": layout.grid_split_field,
                    "preview_text": layout.preview_text,
                    "field_options": [opt[0] for opt in field_options],
                    "field_labels": {opt[0]: opt[1] for opt in field_options},
                },
                "warnings": warnings
            })
            
        except json.JSONDecodeError:
            return aiohttp_web.json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status=400)
        except Exception as e:
            print(f"[ModelCompare] Error in analyze_config: {e}")
            import traceback
            traceback.print_exc()
            return aiohttp_web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    @PromptServer.instance.routes.post("/model_compare/validate_layout")
    async def validate_layout_handler(request):
        """
        Validate a custom layout configuration.
        
        Request body:
        {
            "config": { ... },
            "layout": {
                "x_axis": "...",
                "y_axis": "...",
                "nest_levels": [...]
            }
        }
        
        Response:
        {
            "success": true,
            "valid": true,
            "warnings": ["..."],
            "preview_text": "..."
        }
        """
        try:
            data = await request.json()
            config = data.get('config', {})
            layout_data = data.get('layout', {})
            
            # Analyze to get field info
            analysis = analyze_variations(config)
            
            # Create layout object from request
            layout = LayoutRecommendation(
                x_axis=layout_data.get('x_axis'),
                y_axis=layout_data.get('y_axis'),
                nest_levels=layout_data.get('nest_levels', []),
                total_combinations=len(config.get('combinations', [])),
            )
            
            # Validate
            warnings = validate_layout(layout, analysis)
            
            # Generate preview for this layout
            from .grid_preset_analyzer import _format_nested_preview
            if analysis:
                preview = _format_nested_preview(analysis, layout)
            else:
                preview = "No varying dimensions"
            
            return aiohttp_web.json_response({
                "success": True,
                "valid": len([w for w in warnings if w.startswith("Warning:")]) == 0,
                "warnings": warnings,
                "preview_text": preview
            })
            
        except Exception as e:
            return aiohttp_web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    print("[ModelCompare] Registered preset analysis API routes")


# Register routes when module loads
try:
    register_preset_routes()
except Exception as e:
    print(f"[ModelCompare] Warning: Could not register preset routes: {e}")
