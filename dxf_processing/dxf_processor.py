import ezdxf
import math
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DXFProcessor:
    """
    A DXF processor that extracts shapes from DXF files and converts them to point lists.
    Curves are broken down into small segments with angle changes less than 0.5 degrees.
    """
    
    def __init__(self, max_angle_change_degrees: float = 0.1):
        """
        Initialize the DXF processor.
        
        Args:
            max_angle_change_degrees: Maximum angle change between curve segments in degrees
        """
        self.max_angle_change_radians = math.radians(max_angle_change_degrees)
        
    def process_dxf(self, dxf_path: str) -> Dict[str, List[Tuple[float, float]]]:
        """
        Process a DXF file and extract all shapes as point lists.
        
        Args:
            dxf_path: Path to the DXF file
            
        Returns:
            Dictionary mapping shape names to lists of (x, y) coordinate tuples
        """
        try:
            # Load the DXF file
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            shapes = {}
            shape_counter = 0
            
            # Process each entity in the modelspace
            logger.info("Entities found in DXF file:")
            for entity in msp:
                logger.info(f"  - {entity.dxftype()}")
            
            # Reset and process each entity
            for entity in msp:
                shape_name = f"shape_{shape_counter}"
                
                if entity.dxftype() == 'LINE':
                    points = self._process_line(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'CIRCLE':
                    points = self._process_circle(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'ARC':
                    points = self._process_arc(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'LWPOLYLINE':
                    points = self._process_lwpolyline(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'POLYLINE':
                    points = self._process_polyline(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'SPLINE':
                    points = self._process_spline(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'HATCH':
                    points = self._process_hatch(entity)
                    if points:
                        shapes[shape_name] = points
                        shape_counter += 1
                        
                else:
                    logger.info(f"Unsupported entity type: {entity.dxftype()}")
            
            # Merge shapes that share points
            merged_shapes = self._merge_connected_shapes(shapes)
            
            logger.info(f"Processed {len(shapes)} entities, merged into {len(merged_shapes)} shapes")
            return merged_shapes
            
        except Exception as e:
            logger.error(f"Error processing DXF file: {e}")
            return {}
    
    def _process_line(self, entity) -> List[Tuple[float, float]]:
        """Process a LINE entity."""
        start = entity.dxf.start
        end = entity.dxf.end
        return [(start.x, start.y), (end.x, end.y)]
    
    def _process_circle(self, entity) -> List[Tuple[float, float]]:
        """Process a CIRCLE entity by breaking it into small arcs."""
        center = entity.dxf.center
        radius = entity.dxf.radius
        
        # Calculate number of segments needed
        circumference = 2 * math.pi * radius
        segment_length = radius * self.max_angle_change_radians
        num_segments = max(8, int(circumference / segment_length))
        
        points = []
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            points.append((x, y))
        
        # Remove duplicate points
        points = self._remove_duplicate_points(points, min_distance=0.05)
        
        return points
    
    def _process_arc(self, entity) -> List[Tuple[float, float]]:
        """Process an ARC entity by breaking it into small segments."""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = math.radians(entity.dxf.start_angle)
        end_angle = math.radians(entity.dxf.end_angle)
        
        # Normalize angles
        if end_angle <= start_angle:
            end_angle += 2 * math.pi
        
        # Calculate number of segments needed
        arc_length = radius * (end_angle - start_angle)
        segment_length = radius * self.max_angle_change_radians
        num_segments = max(4, int(arc_length / segment_length))
        
        points = []
        for i in range(num_segments + 1):
            angle = start_angle + (end_angle - start_angle) * i / num_segments
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            points.append((x, y))
        
        # Remove duplicate points
        points = self._remove_duplicate_points(points, min_distance=0.05)
        
        return points
    
    def _process_lwpolyline(self, entity) -> List[Tuple[float, float]]:
        """Process a LWPOLYLINE entity with increased point density."""
        original_points = []
        
        for vertex in entity.get_points():
            x, y = vertex[0], vertex[1]
            original_points.append((x, y))
        
        if len(original_points) < 2:
            return original_points
        
        # Interpolate between points to increase density
        interpolated_points = []
        
        for i in range(len(original_points) - 1):
            p1 = original_points[i]
            p2 = original_points[i + 1]
            
            # Add the first point
            interpolated_points.append(p1)
            
            # Calculate distance between points
            distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            
            # Determine number of intermediate points based on distance and angle change
            # For longer segments, add more points
            if distance > 0.1:  # Only interpolate for segments longer than 0.1 units
                # Calculate angle change if we have 3 points
                if i > 0:
                    p0 = original_points[i - 1]
                    angle_change = self._calculate_angle_change(p0, p1, p2)
                    # More points for sharper turns
                    num_intermediate = max(2, int(abs(angle_change) / self.max_angle_change_radians))
                else:
                    num_intermediate = 3  # Default for first segment
                
                # Add intermediate points
                for j in range(1, num_intermediate):
                    t = j / num_intermediate
                    x = p1[0] + t * (p2[0] - p1[0])
                    y = p1[1] + t * (p2[1] - p1[1])
                    interpolated_points.append((x, y))
        
        # Add the last point
        interpolated_points.append(original_points[-1])
        
        # If the polyline is closed, add the first point at the end
        if entity.closed:
            interpolated_points.append(interpolated_points[0])
        
        # Remove duplicate points
        interpolated_points = self._remove_duplicate_points(interpolated_points, min_distance=0.05)
        
        return interpolated_points
    
    def _process_polyline(self, entity) -> List[Tuple[float, float]]:
        """Process a POLYLINE entity."""
        points = []
        
        for vertex in entity.vertices:
            x, y = vertex.dxf.location.x, vertex.dxf.location.y
            points.append((x, y))
        
        # If the polyline is closed, add the first point at the end
        if entity.closed:
            points.append(points[0])
        
        # Remove duplicate points
        points = self._remove_duplicate_points(points, min_distance=0.05)
        
        return points
    
    def _process_spline(self, entity) -> List[Tuple[float, float]]:
        """Process a SPLINE entity by sampling points along the curve."""
        try:
            # Get the spline curve
            spline = entity.construction_tool()
            
            # Check if the spline is closed
            is_closed = entity.closed if hasattr(entity, 'closed') else False
            
            # For splines, we'll sample at regular parameter intervals
            # Use a higher number of segments for smoother splines
            num_segments = 500  # Increased from 100 for smoother curve approximation
            
            points = []
            for i in range(num_segments + 1):
                # Use parameter t from 0 to 1
                t = i / num_segments
                point = spline.point(t)
                points.append((point.x, point.y))
            
            # Validate the spline points for extreme coordinates
            if points:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                width = x_max - x_min
                height = y_max - y_min
                
                # Check for extreme dimensions (likely corrupted or invalid spline)
                if width > 100 or height > 100 or abs(x_max) > 100 or abs(y_max) > 100:
                    logger.warning(f"Spline has extreme coordinates: width={width:.1f}, height={height:.1f}, bounds=({x_min:.1f},{x_max:.1f}),({y_min:.1f},{y_max:.1f})")
                    # Try fallback to control points
                    try:
                        control_points = []
                        for point in entity.control_points:
                            # Handle both point objects and numpy arrays
                            if hasattr(point, 'x') and hasattr(point, 'y'):
                                control_points.append((point.x, point.y))
                            elif hasattr(point, '__len__') and len(point) >= 2:
                                control_points.append((float(point[0]), float(point[1])))
                        
                        # Validate control points
                        if control_points:
                            cx_coords = [p[0] for p in control_points]
                            cy_coords = [p[1] for p in control_points]
                            cx_min, cx_max = min(cx_coords), max(cx_coords)
                            cy_min, cy_max = min(cy_coords), max(cy_coords)
                            c_width = cx_max - cx_min
                            c_height = cy_max - cy_min
                            
                            if c_width < 100 and c_height < 100 and abs(cx_max) < 100 and abs(cy_max) < 100:
                                logger.info("Using control points as fallback for extreme spline")
                                return control_points
                            else:
                                logger.warning("Control points also have extreme coordinates, skipping spline")
                                return []
                        else:
                            logger.warning("No control points available, skipping spline")
                            return []
                    except Exception as e:
                        logger.warning(f"Error getting control points: {e}")
                        return []
            
            # If the spline should be closed but isn't, add the first point at the end
            if is_closed and len(points) > 1:
                first_point = points[0]
                last_point = points[-1]
                distance = math.sqrt((first_point[0] - last_point[0])**2 + (first_point[1] - last_point[1])**2)
                if distance > 0.001:  # If not already closed
                    points.append(first_point)
            
            # Remove duplicate points
            points = self._remove_duplicate_points(points, min_distance=0.05)
            
            return points
            
        except Exception as e:
            logger.warning(f"Error processing spline: {e}")
            # Fallback: try to get control points
            try:
                points = []
                for point in entity.control_points:
                    # Handle both point objects and numpy arrays
                    if hasattr(point, 'x') and hasattr(point, 'y'):
                        points.append((point.x, point.y))
                    elif hasattr(point, '__len__') and len(point) >= 2:
                        points.append((float(point[0]), float(point[1])))
                return points
            except:
                return []
    
    def _merge_connected_shapes(self, shapes: Dict[str, List[Tuple[float, float]]]) -> Dict[str, List[Tuple[float, float]]]:
        """
        Merge shapes that share points into single shapes.
        
        Args:
            shapes: Dictionary of shape names to point lists
            
        Returns:
            Dictionary of merged shapes
        """
        if len(shapes) <= 1:
            return shapes
        
        # Convert to list for easier processing
        shape_list = list(shapes.items())
        merged_shapes = {}
        used_indices = set()
        
        for i, (name1, points1) in enumerate(shape_list):
            if i in used_indices:
                continue
                
            # Start with this shape
            current_points = points1.copy()
            used_indices.add(i)
            
            # Look for shapes that share points with current shape
            changed = True
            while changed:
                changed = False
                for j, (name2, points2) in enumerate(shape_list):
                    if j in used_indices:
                        continue
                    
                    # Check if shapes share any points
                    if self._shapes_share_points(current_points, points2):
                        # Try to merge the shapes
                        merged_result = self._merge_point_lists(current_points, points2)
                        if merged_result is not None:
                            current_points = merged_result
                            used_indices.add(j)
                            changed = True
                            logger.info(f"Merged shapes {name1} and {name2}")
                        else:
                            logger.info(f"Shapes {name1} and {name2} share points but cannot be merged properly")
            
            # Add merged shape
            merged_name = f"merged_shape_{len(merged_shapes)}"
            # Remove duplicates from the merged shape
            current_points = self._remove_duplicate_points(current_points, min_distance=0.05)
            merged_shapes[merged_name] = current_points
        
        return merged_shapes
    
    def _shapes_share_points(self, points1: List[Tuple[float, float]], 
                           points2: List[Tuple[float, float]], 
                           tolerance: float = 0.1) -> bool:
        """
        Check if two shapes share any points within tolerance.
        
        Args:
            points1: First shape's points
            points2: Second shape's points
            tolerance: Distance tolerance for considering points the same
            
        Returns:
            True if shapes share points, False otherwise
        """
        for p1 in points1:
            for p2 in points2:
                distance = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                if distance <= tolerance:
                    return True
        return False
    
    def _merge_point_lists(self, points1: List[Tuple[float, float]], 
                          points2: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Merge two point lists, removing duplicates and ensuring continuity.
        
        Args:
            points1: First point list
            points2: Second point list
            
        Returns:
            Merged point list
        """
        # Start with first list
        merged = points1.copy()
        
        # Find the best connection point
        best_connection = None
        min_distance = float('inf')
        
        # Check all possible connections
        for i, p1 in enumerate(points1):
            for j, p2 in enumerate(points2):
                # Check end of points1 to start of points2
                if i == len(points1) - 1:
                    distance = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                    if distance < min_distance:
                        min_distance = distance
                        best_connection = ('end_to_start', i, j)
                
                # Check end of points2 to start of points1
                if j == len(points2) - 1:
                    distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                    if distance < min_distance:
                        min_distance = distance
                        best_connection = ('start_to_end', i, j)
        
        # Apply the best connection only if it's within reasonable tolerance
        if best_connection and min_distance < 0.1:  # 0.1 unit tolerance (same as point sharing)
            connection_type, i, j = best_connection
            if connection_type == 'end_to_start':
                # Add points2 after points1
                merged.extend(points2)
            else:  # start_to_end
                # Add points1 after points2
                merged = points2 + merged
        else:
            # No good connection found - don't merge these shapes
            # Return None to indicate that merging should not occur
            return None
        
        return merged
    
    def _process_hatch(self, entity) -> List[Tuple[float, float]]:
        """Process a HATCH entity by extracting its boundary paths."""
        try:
            points = []
            
            # Get the hatch boundary paths
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    for vertex in path.vertices:
                        points.append((vertex.x, vertex.y))
                elif hasattr(path, 'get_points'):
                    for point in path.get_points():
                        points.append((point[0], point[1]))
            
            return points
            
        except Exception as e:
            logger.warning(f"Error processing hatch: {e}")
            return []
    
    def _remove_duplicate_points(self, points: List[Tuple[float, float]], 
                                min_distance: float = 0.01) -> List[Tuple[float, float]]:
        """
        Remove duplicate or near-duplicate points from a point list.
        
        Args:
            points: List of (x, y) coordinate tuples
            min_distance: Minimum distance between consecutive points
            
        Returns:
            Filtered point list with duplicates removed
        """
        if len(points) <= 1:
            return points
        
        filtered_points = [points[0]]  # Always keep the first point
        
        for i in range(1, len(points)):
            current_point = points[i]
            last_point = filtered_points[-1]
            
            # Check for exact duplicates first (handles floating point precision issues)
            if (abs(current_point[0] - last_point[0]) < 1e-10 and 
                abs(current_point[1] - last_point[1]) < 1e-10):
                # Exact duplicate - skip this point
                continue
            
            # Calculate distance to last kept point
            distance = math.sqrt((current_point[0] - last_point[0])**2 + 
                               (current_point[1] - last_point[1])**2)
            
            # Only add point if it's far enough from the last kept point
            if distance >= min_distance:
                filtered_points.append(current_point)
        
        logger.info(f"Removed {len(points) - len(filtered_points)} duplicate points "
                   f"({len(points)} -> {len(filtered_points)})")
        
        return filtered_points
    
    def _calculate_angle_change(self, p1: Tuple[float, float], 
                               p2: Tuple[float, float], 
                               p3: Tuple[float, float]) -> float:
        """
        Calculate the angle change between three consecutive points.
        
        Args:
            p1, p2, p3: Three consecutive points as (x, y) tuples
            
        Returns:
            Angle change in radians
        """
        # Calculate vectors
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        
        # Calculate magnitudes
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if  mag1 == 0 or mag2 == 0:
            return 0
        
        # Calculate dot product
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        
        # Calculate angle
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
        
        return math.acos(cos_angle)


def main():
    """Test the DXF processor with the provided DXF file."""
    processor = DXFProcessor()
    
    # Test with the provided DXF file
    dxf_path = "/Users/peterbriggs/Downloads/circle_test_formatted.dxf"
    
    try:
        shapes = processor.process_dxf(dxf_path)
        
        print(f"Found {len(shapes)} shapes:")
        for shape_name, points in shapes.items():
            print(f"{shape_name}: {len(points)} points")
            if points:
                print(f"  First point: {points[0]}")
                print(f"  Last point: {points[-1]}")
                print(f"  Bounds: X({min(p[0] for p in points):.3f}, {max(p[0] for p in points):.3f}), "
                      f"Y({min(p[1] for p in points):.3f}, {max(p[1] for p in points):.3f})")
            print()
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main() 