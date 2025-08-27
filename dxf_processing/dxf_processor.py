import ezdxf
from ezdxf.addons import drawing
from ezdxf.path import make_path, Path
from ezdxf import path
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
        
    def process_dxf_basic(self, dxf_path: str, min_distance: float = 0.1) -> Dict[str, List[Tuple[float, float]]]:
        """
        Process DXF file using basic approach with point reduction, centering, and positioning.
        Uses simple spline approximation, reduces points to specified spacing, then applies
        the same positioning and grouping logic as the full processor.
        
        Args:
            dxf_path: Path to the DXF file
            min_distance: Minimum distance between points in inches
            
        Returns:
            Dictionary mapping shape names to lists of (x, y) coordinate tuples
        """
        try:
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            shapes = {}
            shape_counter = 0
            
            logger.info("Processing entities with basic approach:")
            for entity in msp:
                logger.info(f"  - {entity.dxftype()}")
                
                if entity.dxftype() == "SPLINE":
                    try:
                        # Get spline construction tool
                        tool = entity.construction_tool()
                        
                        logger.info(f"    Spline degree: {entity.dxf.degree}")
                        logger.info(f"    Control points: {len(entity.control_points)}")
                        
                        # Basic approximation
                        spline_points = tool.approximate(segments=50)
                        points = []
                        for point in spline_points:
                            points.append((point.x, point.y))
                        
                        # Reduce points to specified spacing
                        reduced_points = self._reduce_points_by_distance(points, min_distance)
                        
                        if reduced_points and len(reduced_points) >= 2:
                            shape_name = f"shape_{shape_counter}"
                            shapes[shape_name] = reduced_points
                            shape_counter += 1
                            
                    except Exception as e:
                        logger.warning(f"    Error processing spline: {e}")
                
                # Handle other entity types with basic processing
                elif entity.dxftype() == 'LINE':
                    points = self._process_line(entity)
                    if points:
                        shapes[f"shape_{shape_counter}"] = points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'CIRCLE':
                    points = self._process_circle(entity)
                    if points:
                        # Reduce points for circles too
                        reduced_points = self._reduce_points_by_distance(points, min_distance)
                        shapes[f"shape_{shape_counter}"] = reduced_points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'ARC':
                    points = self._process_arc(entity)
                    if points:
                        # Reduce points for arcs too
                        reduced_points = self._reduce_points_by_distance(points, min_distance)
                        shapes[f"shape_{shape_counter}"] = reduced_points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'LWPOLYLINE':
                    points = self._process_lwpolyline(entity)
                    if points:
                        # Reduce points for polylines too
                        reduced_points = self._reduce_points_by_distance(points, min_distance)
                        shapes[f"shape_{shape_counter}"] = reduced_points
                        shape_counter += 1
                        
                elif entity.dxftype() == 'POLYLINE':
                    points = self._process_polyline(entity)
                    if points:
                        # Reduce points for polylines too
                        reduced_points = self._reduce_points_by_distance(points, min_distance)
                        shapes[f"shape_{shape_counter}"] = reduced_points
                        shape_counter += 1
                        
                else:
                    logger.info(f"Unsupported entity type: {entity.dxftype()}")
            
            if not shapes:
                return {}
            
            # Apply the same post-processing as the full processor
            # 1. Merge shapes that share points
            merged_shapes = self._merge_connected_shapes(shapes)
            
            # 2. Position shapes with bottom-left justification (1" X buffer, 3" Y buffer)
            positioned_shapes = self._position_shapes_bottom_left(merged_shapes, x_buffer_inches=1.0, y_buffer_inches=3.0)
            
            logger.info(f"Processed {len(shapes)} entities with basic approach, merged into {len(merged_shapes)} shapes")
            return positioned_shapes
                
        except Exception as e:
            logger.error(f"Error processing DXF file with basic approach: {e}")
            return {}

    def process_dxf(self, dxf_path: str) -> Dict[str, List[Tuple[float, float]]]:
        """
        Process a DXF file using the basic approach with 0.1" point spacing.
        
        Args:
            dxf_path: Path to the DXF file
            
        Returns:
            Dictionary mapping shape names to lists of (x, y) coordinate tuples
        """
        return self.process_dxf_basic(dxf_path, min_distance=0.1)
    
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
        """Process a SPLINE entity by sampling points along the curve, preserving sharp corners."""
        try:
            # First try to get control points to detect sharp corners
            control_points = []
            try:
                for point in entity.control_points:
                    if hasattr(point, 'x') and hasattr(point, 'y'):
                        control_points.append((point.x, point.y))
                    elif hasattr(point, '__len__') and len(point) >= 2:
                        control_points.append((float(point[0]), float(point[1])))
            except:
                control_points = []
            
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
            
            # If we have control points, ensure sharp corners are preserved
            if len(control_points) >= 3:
                points = self._preserve_sharp_corners_in_spline(points, control_points)
            
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
        Merge two point lists by connecting them at shared endpoints, avoiding duplicates.
        
        Args:
            points1: First point list
            points2: Second point list
            
        Returns:
            Merged point list or None if no proper connection found
        """
        tolerance = 0.1
        
        # Get endpoints of both lists
        p1_start, p1_end = points1[0], points1[-1]
        p2_start, p2_end = points2[0], points2[-1]
        
        # Check all possible connections and find the best one
        connections = []
        
        # End of points1 connects to start of points2
        dist = math.sqrt((p1_end[0] - p2_start[0])**2 + (p1_end[1] - p2_start[1])**2)
        if dist < tolerance:
            connections.append(('end_to_start', dist))
            
        # End of points1 connects to end of points2 (reverse points2)
        dist = math.sqrt((p1_end[0] - p2_end[0])**2 + (p1_end[1] - p2_end[1])**2)
        if dist < tolerance:
            connections.append(('end_to_end', dist))
            
        # Start of points1 connects to end of points2
        dist = math.sqrt((p1_start[0] - p2_end[0])**2 + (p1_start[1] - p2_end[1])**2)
        if dist < tolerance:
            connections.append(('start_to_end', dist))
            
        # Start of points1 connects to start of points2 (reverse points2)
        dist = math.sqrt((p1_start[0] - p2_start[0])**2 + (p1_start[1] - p2_start[1])**2)
        if dist < tolerance:
            connections.append(('start_to_start', dist))
        
        if not connections:
            return None
            
        # Use the connection with the smallest distance
        best_connection = min(connections, key=lambda x: x[1])[0]
        
        # Merge based on the best connection
        if best_connection == 'end_to_start':
            # points1 + points2 (skip duplicate endpoint)
            merged = points1 + points2[1:]
        elif best_connection == 'end_to_end':
            # points1 + reversed points2 (skip duplicate endpoint)
            merged = points1 + list(reversed(points2))[1:]
        elif best_connection == 'start_to_end':
            # points2 + points1 (skip duplicate endpoint)
            merged = points2 + points1[1:]
        elif best_connection == 'start_to_start':
            # reversed points2 + points1 (skip duplicate endpoint)
            merged = list(reversed(points2)) + points1[1:]
        
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
    
    def _preserve_sharp_corners_in_spline(self, spline_points: List[Tuple[float, float]], 
                                         control_points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Preserve sharp corners from control points in spline tessellation.
        
        Args:
            spline_points: Tessellated spline points
            control_points: Original control points
            
        Returns:
            Modified point list with sharp corners preserved
        """
        if len(control_points) < 3:
            return spline_points
        
        # Find sharp corners in control points (angle changes > 45 degrees)
        corner_threshold = math.radians(45.0)
        sharp_corners = []
        
        for i in range(1, len(control_points) - 1):
            angle_change = self._calculate_angle_change(control_points[i-1], control_points[i], control_points[i+1])
            if angle_change > corner_threshold:
                sharp_corners.append(control_points[i])
        
        if not sharp_corners:
            return spline_points
        
        # For each sharp corner, find the closest point in the spline and replace it
        result_points = spline_points.copy()
        
        for corner in sharp_corners:
            # Find closest point in tessellated spline
            min_distance = float('inf')
            closest_index = 0
            
            for i, point in enumerate(result_points):
                distance = math.sqrt((point[0] - corner[0])**2 + (point[1] - corner[1])**2)
                if distance < min_distance:
                    min_distance = distance
                    closest_index = i
            
            # Replace the closest point with the exact corner point
            if min_distance < 0.5:  # Only if reasonably close
                result_points[closest_index] = corner
                logger.info(f"Preserved sharp corner at ({corner[0]:.3f}, {corner[1]:.3f})")
        
        return result_points
    
    def _force_rectangle_corners(self, shapes: Dict[str, List[Tuple[float, float]]]) -> Dict[str, List[Tuple[float, float]]]:
        """
        Force sharp corners at rectangle vertices by finding and replacing rounded corner points.
        
        Args:
            shapes: Dictionary of shape names to point lists
            
        Returns:
            Dictionary with sharp rectangle corners forced
        """
        corrected_shapes = {}
        
        for shape_name, points in shapes.items():
            if len(points) < 4:
                corrected_shapes[shape_name] = points
                continue
            
            # Find bounding box
            x_coords = [p[0] for p in points]
            y_coords = [p[1] for p in points]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            
            # Define the 4 exact corner points
            corners = [
                (x_min, y_min),  # bottom-left
                (x_max, y_min),  # bottom-right  
                (x_max, y_max),  # top-right
                (x_min, y_max)   # top-left
            ]
            
            # For each corner, find the closest point and replace it
            result_points = points.copy()
            corners_replaced = 0
            
            for corner in corners:
                min_distance = float('inf')
                closest_index = 0
                
                for i, point in enumerate(result_points):
                    distance = math.sqrt((point[0] - corner[0])**2 + (point[1] - corner[1])**2)
                    if distance < min_distance:
                        min_distance = distance
                        closest_index = i
                
                # Replace if reasonably close (within 0.5 units)
                if min_distance < 0.5:
                    result_points[closest_index] = corner
                    corners_replaced += 1
            
            corrected_shapes[shape_name] = result_points
            if corners_replaced > 0:
                logger.info(f"Forced {corners_replaced} sharp rectangle corners in {shape_name}")
        
        return corrected_shapes
    
    def _position_shapes_bottom_left(self, shapes: Dict[str, List[Tuple[float, float]]], 
                                    x_buffer_inches: float = 1.0, 
                                    y_buffer_inches: float = 1.0) -> Dict[str, List[Tuple[float, float]]]:
        """
        Position all shapes so they are bottom-left justified with separate X and Y buffers.
        
        Args:
            shapes: Dictionary mapping shape names to lists of (x, y) coordinate tuples
            x_buffer_inches: Buffer distance in inches from the left edge
            y_buffer_inches: Buffer distance in inches from the bottom edge
            
        Returns:
            Dictionary with the same shape names but translated coordinates
        """
        if not shapes:
            return shapes
        
        # Calculate the overall bounding box of all shapes
        all_points = []
        for points in shapes.values():
            all_points.extend(points)
        
        if not all_points:
            return shapes
        
        # Find the current bounds
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)
        
        logger.info(f"Original bounds: X({min_x:.3f}, {max_x:.3f}), Y({min_y:.3f}, {max_y:.3f})")
        
        # Calculate translation to move shapes to bottom-left with separate buffers
        translate_x = x_buffer_inches - min_x
        translate_y = y_buffer_inches - min_y
        
        logger.info(f"Translating by: X={translate_x:.3f}, Y={translate_y:.3f}")
        
        # Apply translation to all shapes
        positioned_shapes = {}
        for shape_name, points in shapes.items():
            translated_points = [(p[0] + translate_x, p[1] + translate_y) for p in points]
            positioned_shapes[shape_name] = translated_points
        
        # Log the new bounds
        new_all_points = []
        for points in positioned_shapes.values():
            new_all_points.extend(points)
        
        new_min_x = min(p[0] for p in new_all_points)
        new_max_x = max(p[0] for p in new_all_points)
        new_min_y = min(p[1] for p in new_all_points)
        new_max_y = max(p[1] for p in new_all_points)
        
        logger.info(f"New bounds: X({new_min_x:.3f}, {new_max_x:.3f}), Y({new_min_y:.3f}, {new_max_y:.3f})")
        
        return positioned_shapes
    
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

    def _process_path(self, entity_path: Path) -> List[Tuple[float, float]]:
        """
        Process an ezdxf Path object to extract points with better corner preservation.
        
        Args:
            entity_path: ezdxf Path object
            
        Returns:
            List of (x, y) coordinate tuples
        """
        points = []
        
        try:
            # Use path flattening for better control over tessellation
            # This approach respects the geometric intent better than direct spline sampling
            flattened = entity_path.flattening(distance=0.05, segments=4)
            
            for vertex in flattened:
                if hasattr(vertex, 'x') and hasattr(vertex, 'y'):
                    points.append((vertex.x, vertex.y))
                elif len(vertex) >= 2:
                    points.append((float(vertex[0]), float(vertex[1])))
            
            # Remove duplicates
            points = self._remove_duplicate_points(points, min_distance=0.05)
            
            return points
            
        except Exception as e:
            logger.warning(f"Error processing path: {e}")
            # Fallback to approximation
            try:
                approximate_points = []
                for vertex in entity_path.approximate(segments=50):
                    if hasattr(vertex, 'x') and hasattr(vertex, 'y'):
                        approximate_points.append((vertex.x, vertex.y))
                    elif len(vertex) >= 2:
                        approximate_points.append((float(vertex[0]), float(vertex[1])))
                
                return self._remove_duplicate_points(approximate_points, min_distance=0.05)
                
            except Exception as e2:
                logger.warning(f"Error with path approximation: {e2}")
                return []

    def _reduce_points_by_distance(self, points: List[Tuple[float, float]], min_distance: float = 0.1) -> List[Tuple[float, float]]:
        """
        Reduce points to only include points that are at least min_distance apart.
        
        Args:
            points: Original list of points
            min_distance: Minimum distance between points in inches
            
        Returns:
            Filtered list of points
        """
        if len(points) <= 1:
            return points
        
        reduced_points = [points[0]]  # Always keep first point
        
        for point in points[1:]:
            last_point = reduced_points[-1]
            # Calculate distance to last kept point
            distance = ((point[0] - last_point[0])**2 + (point[1] - last_point[1])**2)**0.5
            
            # Only add point if it's far enough from the last kept point
            if distance >= min_distance:
                reduced_points.append(point)
        
        logger.info(f"Reduced from {len(points)} to {len(reduced_points)} points ({min_distance}\" spacing)")
        return reduced_points


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