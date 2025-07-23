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
    Works entirely in inches - no unit conversion.
    """
    
    def __init__(self, max_angle_change_degrees: float = 0.1):
        """Initialize the DXF processor.
        
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
            Dictionary mapping shape names to lists of (x, y) coordinate tuples in inches
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
        segment_length = 0.01  # 0.01 inch segments
        num_segments = max(64, int(circumference / segment_length))
        
        points = []
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            points.append((x, y))
            
        return points
    
    def _process_arc(self, entity) -> List[Tuple[float, float]]:
        """Process an ARC entity by breaking it into small segments."""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = math.radians(entity.dxf.start_angle)
        end_angle = math.radians(entity.dxf.end_angle)
        
        # Ensure end_angle > start_angle
        if end_angle <= start_angle:
            end_angle += 2 * math.pi
            
        # Calculate number of segments needed
        arc_length = radius * (end_angle - start_angle)
        segment_length = 0.01  # 0.01 inch segments
        num_segments = max(32, int(arc_length / segment_length))
        
        points = []
        for i in range(num_segments + 1):
            angle = start_angle + (end_angle - start_angle) * i / num_segments
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            points.append((x, y))
            
        return points
    
    def _process_lwpolyline(self, entity) -> List[Tuple[float, float]]:
        """Process a LWPOLYLINE entity with increased point density."""
        original_points = []
        
        for vertex in entity.get_points():
            x, y = vertex[0], vertex[1]
            original_points.append((x, y))
        
        # If it's a closed polyline, ensure the last point connects to the first
        if entity.closed and original_points and original_points[0] != original_points[-1]:
            original_points.append(original_points[0])
        
        # Add intermediate points for better curve representation
        refined_points = []
        for i in range(len(original_points) - 1):
            p1 = original_points[i]
            p2 = original_points[i + 1]
            
            refined_points.append(p1)
            
            # Add intermediate points if the segment is long
            distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            if distance > 0.1:  # If segment is longer than 0.1 inches
                num_intermediate = int(distance / 0.01)  # One point every 0.01 inches
                for j in range(1, num_intermediate):
                    t = j / num_intermediate
                    x = p1[0] + t * (p2[0] - p1[0])
                    y = p1[1] + t * (p2[1] - p1[1])
                    refined_points.append((x, y))
        
        if original_points:
            refined_points.append(original_points[-1])
        
        return refined_points
    
    def _process_polyline(self, entity) -> List[Tuple[float, float]]:
        """Process a POLYLINE entity."""
        points = []
        
        for vertex in entity.vertices:
            x, y = vertex.dxf.location.x, vertex.dxf.location.y
            points.append((x, y))
        
        # If it's a closed polyline, ensure the last point connects to the first
        if entity.closed and points and points[0] != points[-1]:
            points.append(points[0])
        
        return points
    
    def _process_spline(self, entity) -> List[Tuple[float, float]]:
        """Process a SPLINE entity by flattening it into line segments."""
        try:
            # Try to flatten the spline
            points = list(entity.flattening(0.01))  # 0.01 inch tolerance
            
            # Check if the spline has extreme coordinates that might cause issues
            if points:
                x_coords = [p[0] for p in points if len(p) >= 2]
                y_coords = [p[1] for p in points if len(p) >= 2]
                
                if x_coords and y_coords:
                    x_range = max(x_coords) - min(x_coords)
                    y_range = max(y_coords) - min(y_coords)
                    
                    # If the spline has extreme dimensions, use control points as fallback
                    if x_range > 1000 or y_range > 1000:
                        logger.warning(f"Spline has extreme coordinates: width={x_range:.1f}, height={y_range:.1f}, bounds=({min(x_coords):.1f},{max(x_coords):.1f}),({min(y_coords):.1f},{max(y_coords):.1f})")
                        logger.info("Using control points as fallback for extreme spline")
                        
                        # Use control points as fallback
                        control_points = entity.control_points
                        if control_points:
                            points = [(cp.x, cp.y) for cp in control_points]
                        else:
                            return []
            
            # Convert to list of tuples and filter out invalid points
            result = []
            for point in points:
                if len(point) >= 2:
                    result.append((point[0], point[1]))
            
            return result
            
        except Exception as e:
            logger.warning(f"Error processing spline, using control points: {e}")
            try:
                # Fallback to control points
                control_points = entity.control_points
                if control_points:
                    return [(cp.x, cp.y) for cp in control_points]
            except:
                pass
            return []
    
    def _merge_connected_shapes(self, shapes: Dict[str, List[Tuple[float, float]]]) -> Dict[str, List[Tuple[float, float]]]:
        """Merge shapes that share points within a tolerance."""
        if not shapes:
            return {}
        
        # Start with all shapes
        remaining_shapes = list(shapes.items())
        merged_shapes = {}
        
        while remaining_shapes:
            current_name, current_points = remaining_shapes.pop(0)
            merged_points = current_points.copy()
            
            # Try to merge with remaining shapes
            i = 0
            while i < len(remaining_shapes):
                other_name, other_points = remaining_shapes[i]
                
                if self._shapes_share_points(merged_points, other_points, tolerance=0.1):
                    # Merge the shapes
                    merged_points = self._merge_point_lists(merged_points, other_points)
                    logger.info(f"Merged shapes {current_name} and {other_name}")
                    remaining_shapes.pop(i)
                else:
                    i += 1
            
            # Remove duplicate points from merged shape
            merged_points = self._remove_duplicate_points(merged_points)
            
            merged_shapes[current_name] = merged_points
        
        return merged_shapes
    
    def _shapes_share_points(self, points1: List[Tuple[float, float]], 
                           points2: List[Tuple[float, float]], 
                           tolerance: float = 0.1) -> bool:
        """Check if two shapes share any points within tolerance."""
        for p1 in points1:
            for p2 in points2:
                distance = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                if distance < tolerance:
                    return True
        return False
    
    def _merge_point_lists(self, points1: List[Tuple[float, float]], 
                          points2: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Merge two point lists, avoiding duplicates."""
        merged = points1.copy()
        
        for point in points2:
            # Check if point is already in merged list
            is_duplicate = False
            for existing_point in merged:
                distance = math.sqrt((point[0] - existing_point[0])**2 + (point[1] - existing_point[1])**2)
                if distance < 0.01:  # 0.01 inch tolerance for duplicates
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                merged.append(point)
        
        return merged
    
    def _process_hatch(self, entity) -> List[Tuple[float, float]]:
        """Process a HATCH entity by extracting boundary points."""
        points = []
        
        try:
            # Get the hatch boundary paths
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    for vertex in path.vertices:
                        points.append((vertex.x, vertex.y))
                elif hasattr(path, 'get_points'):
                    for point in path.get_points():
                        points.append((point[0], point[1]))
        except Exception as e:
            logger.warning(f"Error processing hatch: {e}")
        
        return points
    
    def _remove_duplicate_points(self, points: List[Tuple[float, float]], 
                                min_distance: float = 0.01) -> List[Tuple[float, float]]:
        """Remove duplicate points that are very close together."""
        if len(points) <= 1:
            return points
        
        result = [points[0]]
        original_count = len(points)
        
        for point in points[1:]:
            # Check if this point is too close to the last point in result
            last_point = result[-1]
            distance = math.sqrt((point[0] - last_point[0])**2 + (point[1] - last_point[1])**2)
            
            if distance >= min_distance:
                result.append(point)
        
        removed_count = original_count - len(result)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate points ({original_count} -> {len(result)})")
        
        return result
    
    def _calculate_angle_change(self, p1: Tuple[float, float], 
                               p2: Tuple[float, float], 
                               p3: Tuple[float, float]) -> float:
        """Calculate the angle change between three points."""
        # Vector from p1 to p2
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        # Vector from p2 to p3
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        
        # Calculate magnitudes
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        # Calculate dot product
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        
        # Calculate angle
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to valid range
        angle = math.acos(cos_angle)
        
        return angle

def main():
    """Test the DXF processor."""
    processor = DXFProcessor()
    
    # Test with a sample DXF file
    dxf_path = "test_2.dxf"
    try:
        shapes = processor.process_dxf(dxf_path)
        print(f"Processed {len(shapes)} shapes from {dxf_path}")
        
        for shape_name, points in shapes.items():
            print(f"{shape_name}: {len(points)} points")
            if points:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                print(f"  X range: {min(x_coords):.3f} to {max(x_coords):.3f}")
                print(f"  Y range: {min(y_coords):.3f} to {max(y_coords):.3f}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 