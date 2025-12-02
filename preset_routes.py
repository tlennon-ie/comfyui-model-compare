"""
API Routes for Grid Preset Analysis

Provides endpoints for analyzing model compare configurations
without running the full generation pipeline.
"""

import json
from dataclasses import asdict

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
        analyze_config,
        analyze_from_variation_lists,
        LayoutRecommendation,
        FieldAnalysis,
    )
    
    @PromptServer.instance.routes.post("/model_compare/analyze_config")
    async def analyze_config_handler(request):
        """
        Analyze a MODEL_COMPARE_CONFIG to determine optimal grid layout.
        
        Request body:
        {
            "config": { ... },  // MODEL_COMPARE_CONFIG data (raw variation lists)
            "max_per_grid": 500  // Optional: max images per grid
        }
        
        Response:
        {
            "success": true,
            "analysis": {
                "fields": { field_name: { display_name, values, value_count, priority }, ... },
                "total_combinations": 128,
            },
            "layout": {
                "x_axis": "lora_strength",
                "y_axis": "model", 
                "nest_levels": ["prompt"],
                "strategy": "nested",
                "explanation": "...",
                "num_grids": 2,
                "combinations_per_grid": 64,
            },
            "warnings": []
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
            
            # Analyze configuration and get optimal layout
            layout = analyze_config(config, max_per_grid)
            
            # Build response
            analysis_dict = {}
            field_options = []
            
            if layout.field_analysis:
                for field_name, field_analysis in layout.field_analysis.items():
                    analysis_dict[field_name] = {
                        "display_name": field_analysis.display_name,
                        "values": [str(v) for v in field_analysis.values],
                        "value_count": field_analysis.value_count,
                        "priority": field_analysis.priority,
                        "is_row_candidate": field_analysis.is_row_candidate,
                        "is_col_candidate": field_analysis.is_col_candidate,
                        "is_nest_candidate": field_analysis.is_nest_candidate,
                    }
                    field_options.append({
                        "value": field_name,
                        "label": field_analysis.display_name,
                        "count": field_analysis.value_count,
                    })
            
            # Sort field options by priority
            field_options.sort(key=lambda x: analysis_dict.get(x["value"], {}).get("priority", 0), reverse=True)
            
            return aiohttp_web.json_response({
                "success": True,
                "analysis": {
                    "fields": analysis_dict,
                    "total_combinations": layout.total_combinations,
                },
                "layout": {
                    "x_axis": layout.x_axis,
                    "y_axis": layout.y_axis,
                    "nest_levels": layout.nest_levels,
                    "strategy": layout.strategy,
                    "explanation": layout.explanation,
                    "num_grids": layout.num_grids,
                    "combinations_per_grid": layout.combinations_per_grid,
                    "field_options": field_options,
                },
                "warnings": []
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
    
    print("[ModelCompare] Registered preset analysis API routes")


# Register routes when module loads
try:
    register_preset_routes()
except Exception as e:
    print(f"[ModelCompare] Warning: Could not register preset routes: {e}")
