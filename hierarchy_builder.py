"""
Hierarchy Builder Module

Creates multi-level nested grid structures supporting arbitrary nesting depth.
Extends HTML generation to support >2 levels with recursive table structure.
"""

from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass
from collections import OrderedDict, defaultdict


@dataclass
class HierarchyLevel:
    """Represents one level in the hierarchy."""
    field: str
    values: List[Any]
    depth: int  # 0 = outermost, increasing inward
    parent_combinations: List[Tuple] = None
    
    def __post_init__(self):
        if self.parent_combinations is None:
            self.parent_combinations = []


class HierarchyTree:
    """
    Represents a complete hierarchy tree.
    
    Structure:
    {
        'value1': {
            'children': {
                'child_value1': {
                    'children': {...},
                    'images': [idx1, idx2, ...]
                },
                'child_value2': {...}
            },
            'images': []  # If leaf
        }
    }
    """
    
    def __init__(self, hierarchy_fields: List[str]):
        self.hierarchy_fields = hierarchy_fields
        self.root = {}
    
    def add_entry(self, field_values: Tuple[Any, ...], image_index: int) -> None:
        """
        Add an image to the tree at the specified path.
        
        Args:
            field_values: Tuple of values matching hierarchy_fields order
            image_index: Index of image in original array
        """
        if not self.hierarchy_fields:
            return
        
        current = self.root
        
        # Navigate/create path for all levels except last
        for level, field in enumerate(self.hierarchy_fields[:-1]):
            value = field_values[level] if level < len(field_values) else None
            
            if value not in current:
                current[value] = {'children': {}, 'images': []}
            
            current = current[value]['children']
        
        # Add to leaf level
        leaf_value = field_values[-1] if len(field_values) > 0 else None
        if leaf_value not in current:
            current[leaf_value] = {'children': {}, 'images': []}
        
        current[leaf_value]['images'].append(image_index)
    
    def get_paths(self) -> List[Tuple]:
        """Get all unique paths from root to leaves."""
        paths = []
        
        def traverse(node: Dict, current_path: Tuple):
            if not node.get('children'):
                # Leaf node
                if node.get('images'):
                    paths.append(current_path)
            else:
                # Internal node
                for value, child_node in node['children'].items():
                    traverse(child_node, current_path + (value,))
        
        for root_value, root_node in self.root.items():
            traverse(root_node, (root_value,))
        
        return paths
    
    def get_cell_images(self, row_path: Tuple, col_path: Tuple) -> List[int]:
        """
        Get images at intersection of row and column paths.
        
        For multi-level grids, a "row path" might be (model_A, sampler_euler)
        and a "col path" might be (cfg_7.5, strength_0.8).
        """
        # This depends on how row/col hierarchies are distributed
        # For now, return combined images from both paths
        combined = set()
        
        # Find images under row path
        current = self.root
        for value in row_path:
            if value in current:
                current = current[value]['children']
                for img in current.get(value, {}).get('images', []):
                    combined.add(img)
        
        return list(combined)
    
    def print_tree(self, indent: int = 0) -> None:
        """Print tree structure for debugging."""
        def print_node(node: Dict, prefix: str = ""):
            for value, child in node.items():
                print(f"{prefix}{value} (images: {len(child.get('images', []))})")
                if child.get('children'):
                    print_node(child['children'], prefix + "  ")
        
        print_node(self.root)


class HierarchyBuilder:
    """
    Builds hierarchy trees from image combinations.
    Supports arbitrary nesting depth with ragged hierarchies.
    """
    
    def __init__(self):
        self.row_tree = None
        self.col_tree = None
        self.cell_map = {}  # (row_path, col_path) -> image_index
    
    def build_from_combinations(
        self,
        combinations: List[Dict],
        row_hierarchy: List[str],
        col_hierarchy: List[str],
        get_field_value,  # Callback to extract field value from combination
    ) -> Tuple[HierarchyTree, HierarchyTree, Dict]:
        """
        Build hierarchy trees from list of combinations.
        
        Args:
            combinations: List of combination dicts with parameters
            row_hierarchy: List of field names for rows (outer to inner)
            col_hierarchy: List of field names for columns (outer to inner)
            get_field_value: Function(combo, field) -> value
        
        Returns:
            (row_tree, col_tree, cell_map)
        """
        self.row_tree = HierarchyTree(row_hierarchy)
        self.col_tree = HierarchyTree(col_hierarchy)
        self.cell_map = {}
        
        for idx, combo in enumerate(combinations):
            # Extract field values for this combination
            row_values = tuple(
                get_field_value(combo, field) for field in row_hierarchy
            ) if row_hierarchy else ()
            
            col_values = tuple(
                get_field_value(combo, field) for field in col_hierarchy
            ) if col_hierarchy else ()
            
            # Add to trees
            if row_hierarchy:
                self.row_tree.add_entry(row_values, idx)
            if col_hierarchy:
                self.col_tree.add_entry(col_values, idx)
            
            # Map cell to image
            self.cell_map[(row_values, col_values)] = idx
        
        return self.row_tree, self.col_tree, self.cell_map
    
    def get_valid_cells(self) -> List[Tuple[Tuple, Tuple]]:
        """Get all cells that have at least one image."""
        return list(self.cell_map.keys())
    
    def get_cell_images(self, row_path: Tuple, col_path: Tuple) -> Optional[int]:
        """Get image index for a cell (or None if empty)."""
        return self.cell_map.get((row_path, col_path))
    
    def get_row_paths(self) -> List[Tuple]:
        """Get unique row paths."""
        if self.row_tree is None:
            return [()]
        return self.row_tree.get_paths() if self.row_tree.hierarchy_fields else [()]
    
    def get_col_paths(self) -> List[Tuple]:
        """Get unique column paths."""
        if self.col_tree is None:
            return [()]
        return self.col_tree.get_paths() if self.col_tree.hierarchy_fields else [()]
    
    def get_filtered_row_paths(self) -> List[Tuple]:
        """Get row paths that have at least one image."""
        valid_rows = set()
        for (row_path, col_path) in self.cell_map.keys():
            valid_rows.add(row_path)
        return sorted(valid_rows)
    
    def get_filtered_col_paths(self) -> List[Tuple]:
        """Get column paths that have at least one image."""
        valid_cols = set()
        for (row_path, col_path) in self.cell_map.keys():
            valid_cols.add(col_path)
        return sorted(valid_cols)


class NestedGridLayout:
    """
    Calculates layout dimensions for nested grids.
    Uses y-cursor approach for stacking elements.
    """
    
    def __init__(
        self,
        row_paths: List[Tuple],
        col_paths: List[Tuple],
        row_hierarchy: List[str],
        col_hierarchy: List[str],
    ):
        self.row_paths = row_paths
        self.col_paths = col_paths
        self.row_hierarchy = row_hierarchy
        self.col_hierarchy = col_hierarchy
        
        # Styling parameters
        self.image_width = 512
        self.image_height = 512
        self.gap_size = 4
        self.header_height = 60
        self.header_width = 150
        self.title_height = 80
        
        # Calculated dimensions
        self.grid_width = 0
        self.grid_height = 0
        self.row_header_width = 0
        self.col_header_height = 0
    
    def calculate_dimensions(self) -> Tuple[int, int]:
        """
        Calculate total grid dimensions.
        
        Returns:
            (width, height)
        """
        num_rows = len(self.row_paths)
        num_cols = len(self.col_paths)
        
        if num_rows == 0:
            num_rows = 1
        if num_cols == 0:
            num_cols = 1
        
        # Column headers - one row per hierarchy level
        self.col_header_height = len(self.col_hierarchy) * self.header_height
        
        # Row headers - total width of all levels
        self.row_header_width = len(self.row_hierarchy) * self.header_width
        
        # Content area
        content_width = num_cols * (self.image_width + self.gap_size)
        content_height = num_rows * (self.image_height + self.gap_size)
        
        # Total dimensions
        self.grid_width = self.row_header_width + content_width + self.gap_size
        self.grid_height = (
            self.title_height +
            self.col_header_height +
            content_height +
            self.gap_size
        )
        
        return self.grid_width, self.grid_height
    
    def get_row_header_positions(self) -> List[Tuple[int, int, int, int]]:
        """
        Get (x, y, width, height) for each row header cell.
        
        Returns row headers for first level only (merging happens at render time).
        """
        positions = []
        y = self.title_height + self.col_header_height
        
        for row_idx in range(len(self.row_paths)):
            x = 0
            for level_idx in range(len(self.row_hierarchy)):
                header_w = self.header_width
                positions.append((x, y, header_w, self.image_height))
                x += header_w
            
            y += self.image_height + self.gap_size
        
        return positions
    
    def get_col_header_positions(self) -> List[Tuple[int, int, int, int]]:
        """
        Get (x, y, width, height) for each column header cell.
        
        Returns column headers for first level only (merging happens at render time).
        """
        positions = []
        
        for level_idx in range(len(self.col_hierarchy)):
            y = self.title_height + (level_idx * self.header_height)
            x = self.row_header_width
            
            for col_idx in range(len(self.col_paths)):
                positions.append((x, y, self.image_width, self.header_height))
                x += self.image_width + self.gap_size
        
        return positions
    
    def get_image_position(self, row_idx: int, col_idx: int) -> Tuple[int, int]:
        """Get (x, y) position for image at row_idx, col_idx."""
        x = self.row_header_width + col_idx * (self.image_width + self.gap_size)
        y = (
            self.title_height +
            self.col_header_height +
            row_idx * (self.image_height + self.gap_size)
        )
        return x, y


class HeaderMerger:
    """
    Determines which header cells should be merged based on hierarchy.
    
    For example, if Model A uses Sampler Euler for two different CFG values,
    the "Model A" header should span both CFG columns.
    """
    
    @staticmethod
    def calculate_row_header_spans(
        row_paths: List[Tuple],
        row_hierarchy: List[str],
    ) -> Dict[Tuple, Dict[int, int]]:
        """
        Calculate span for each row header cell.
        
        Returns:
            {
                (path): {level: span_count}
            }
        """
        spans = {}
        
        for idx, path in enumerate(row_paths):
            spans[path] = {}
            
            # For each level, count consecutive rows with same value
            for level in range(len(row_hierarchy)):
                # Count rows ahead with same value at this level
                span = 1
                for next_idx in range(idx + 1, len(row_paths)):
                    next_path = row_paths[next_idx]
                    if level < len(next_path) and level < len(path):
                        if next_path[level] == path[level]:
                            span += 1
                        else:
                            break
                
                spans[path][level] = span
        
        return spans
    
    @staticmethod
    def calculate_col_header_spans(
        col_paths: List[Tuple],
        col_hierarchy: List[str],
    ) -> Dict[Tuple, Dict[int, int]]:
        """
        Calculate span for each column header cell.
        
        Similar to row spans but for columns.
        """
        spans = {}
        
        for idx, path in enumerate(col_paths):
            spans[path] = {}
            
            for level in range(len(col_hierarchy)):
                # Count columns ahead with same value at this level
                span = 1
                for next_idx in range(idx + 1, len(col_paths)):
                    next_path = col_paths[next_idx]
                    if level < len(next_path) and level < len(path):
                        if next_path[level] == path[level]:
                            span += 1
                        else:
                            break
                
                spans[path][level] = span
        
        return spans


class SmartHierarchyDetector:
    """Intelligently detect hierarchy by analyzing per-chain vs cross-chain variation."""
    
    @staticmethod
    def detect_hierarchy(combinations, preferred_rows=None, preferred_cols=None):
        """Detect optimal hierarchy by analyzing variation patterns."""
        if not combinations:
            return [], []
        
        from collections import defaultdict
        
        # Step 1: Find varying fields
        field_values = defaultdict(set)
        for combo in combinations:
            for key, value in combo.items():
                if key.startswith('_'):
                    continue
                if isinstance(value, (list, tuple)):
                    value = tuple(value)
                field_values[key].add(value)
        
        varying_fields = [f for f, vals in field_values.items() if len(vals) > 1]
        if not varying_fields:
            return [], []
        
        # Step 2: Identify chain fields (model-related)
        chain_indicators = ['model', 'base_model', 'diffusion_model', 'model_name', 'model_index', 'checkpoint']
        chain_fields = [f for f in varying_fields if any(ind in f.lower() for ind in chain_indicators)]
        
        if not chain_fields:
            field_counts = {f: len(set(c.get(f) for c in combinations)) for f in varying_fields}
            candidates = [(f, cnt) for f, cnt in field_counts.items() if 2 <= cnt <= 20]
            if candidates:
                chain_fields = [max(candidates, key=lambda x: x[1])[0]]
        
        # Step 3: Find fields static within chains but varying across chains
        cross_chain_static = set()
        if chain_fields:
            chains = defaultdict(list)
            for combo in combinations:
                chain_key = tuple(combo.get(f) for f in chain_fields)
                chains[chain_key].append(combo)
            
            for field in varying_fields:
                if field in chain_fields:
                    continue
                is_static = True
                for chain_combos in chains.values():
                    vals = set(tuple(c.get(field)) if isinstance(c.get(field), (list, tuple)) else c.get(field) for c in chain_combos)
                    if len(vals) > 1:
                        is_static = False
                        break
                if is_static:
                    cross_chain_static.add(field)
        
        # Step 4: Hierarchy candidates (vary within chains)
        hierarchy_candidates = [f for f in varying_fields if f not in cross_chain_static]
        
        # Step 5: Assign to axes
        field_cardinality = {f: len(set(tuple(c.get(f)) if isinstance(c.get(f), (list, tuple)) else c.get(f) for c in combinations)) for f in hierarchy_candidates}
        
        row_fields = []
        col_fields = []
        
        if preferred_rows:
            for f in preferred_rows:
                if f in hierarchy_candidates:
                    row_fields.append(f)
                    hierarchy_candidates.remove(f)
        
        if preferred_cols:
            for f in preferred_cols:
                if f in hierarchy_candidates:
                    col_fields.append(f)
                    hierarchy_candidates.remove(f)
        
        prompt_indicators = ['prompt', 'text', 'description', 'positive', 'negative']
        model_indicators = ['model', 'checkpoint', 'diffusion', 'unet']
        
        for field in hierarchy_candidates:
            field_lower = field.lower()
            cardinality = field_cardinality[field]
            
            if any(ind in field_lower for ind in prompt_indicators):
                row_fields.append(field)
            elif any(ind in field_lower for ind in model_indicators):
                col_fields.append(field)
            elif cardinality > 6:
                row_fields.append(field)
            else:
                col_fields.append(field)
        
        return row_fields, col_fields
