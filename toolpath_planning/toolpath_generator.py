#!/usr/bin/env python3
"""
Drag Knife Toolpath Generator for grblHAL

Generates G-code for drag knife cutting with active A-axis control only at corners.
Between corners, the blade follows passively with no A commands.
"""

from typing import Dict, List, Tuple, Optional
import math
import csv
import os

class ToolpathGenerator():
    """Main class for generating toolpaths."""

    def __init__(self, 
                 cutting_height: float = -0.5,
                 safe_height: float = 0.0,
                 corner_angle_threshold: float = 15.0,
                 feed_rate: float = 6000.0,
                 plunge_rate: float = 6000.0,
                 knife_offset: float = 0.5):
        """Init function."""
        self.corner_threshold = corner_angle_threshold # degrees
        self.drag_offset = knife_offset # inches
        self.toolpath = ""
        self.safe_height_z = safe_height # inches
        self.cut_height_z = cutting_height
        self.feedrate = feed_rate

    def _header(self) -> str:
        """Returns the header for all GCODE files."""
        # TODO add homing at beginning of file
        header = (
            f"; Fabric CNC Toolpath\n"
            f"\n"
            f"G20 ; Set units to inches\n"
            f"G90 ; Set absolute positioning\n"
            f"G54 ; Use work coordinate system (WCS)\n"
            f"G17 ; Select XY plane\n"
            f"G94 ; Feed rate mode (units per minute)\n"
            f"\n"
            f"G0 Z{self.safe_height_z} ; Move to safe height\n"
        )
        return header
    
    def _footer(self) -> str:
        """Returns the footer for all GCODE files."""
        footer = (
            f"\n"
            f"G0 Z{self.safe_height_z} ; Return to safe height\n"
            f"G0 X0 Y0 A0 ; Return to work coordinate origin\n"
            f"M5 ; Spindle off (if applicable)\n"
            f"M2 ; End program"
        )
        return footer        

    def generate_toolpath(self, point_dictionary: Dict[str, List[Tuple[float, float]]]) -> str:
        """Generates toolpath for dxf file."""
        # Save points to CSV file for inspection/debugging
        self._save_points_to_csv(point_dictionary)
        
        self.toolpath = self._header() # overwrites any prior toolpath with header
        shape_count = len(point_dictionary)
        index = 1
        for shape, points in point_dictionary.items():  
            self.toolpath += f"\n"   
            self.toolpath += f"; Shape {index}/{shape_count}: {shape}\n"
            self.toolpath += self._generate_shape_toolpath(points=points)
            index += 1
        self.toolpath += self._footer()
        return self.toolpath

    def _generate_shape_toolpath(self, points: List[Tuple[float, float]]) -> str:
        """Generates toolpath for a single shape."""
        shape_toolpath = ""
        corners = self._find_corners(points)
        print(corners)
        if len(corners) == 0: # if there are no corners
            for index, point in enumerate(points):
                if index == 0: # if just starting out
                    x, y, a = self._get_toolhead_in_position([point, points[index+1]])
                    a_machine_units = a / 360.0  # Convert degrees to machine units (1 inch = 360 degrees)
                    shape_toolpath += (
                        f"G0 X{x} Y{y} A{a_machine_units} ; Move to start\n"
                        f"G0 Z{self.cut_height_z} ; Plunge to cutting height\n"
                    )
                elif index == (len(points)-1): # last point in path
                    x, y = self._calculate_next_xy([point, points[0]])
                    shape_toolpath += f"G1 X{x} Y{y} F{self.feedrate}\n" 
                else: # all other points
                    x, y = self._calculate_next_xy([point, points[index+1]])
                    shape_toolpath += f"G1 X{x} Y{y} F{self.feedrate}\n"  
        else: # at least one corner
            points = self._shuffle_points(points=points, starting_point=corners[0][0]) # shuffle points to start at corner
            corners = self._find_corners(points) # find corners again 
            print(corners)
            for index, point in enumerate(points):
                if index == 0: # if just starting out or if at corner
                    x, y, a = self._get_toolhead_in_position([point, points[index+1]])
                    a_machine_units = a / 360.0  # Convert degrees to machine units (1 inch = 360 degrees)
                    shape_toolpath += (
                        f"G0 X{x} Y{y} A{a_machine_units} ; Move to start\n"
                        f"G0 Z{self.cut_height_z} ; Plunge to cutting height\n"
                    )
                elif index == (len(points)-1): # last point in path
                    x, y = self._calculate_next_xy([point, points[0]])
                    shape_toolpath += f"G1 X{x} Y{y} F{self.feedrate}\n" 
                else: # all other points
                    if any(corner[0] == index for corner in corners):
                        x, y = self._calculate_next_xy([points[index-1], points[index]])
                        shape_toolpath += f"G1 X{x} Y{y} F{self.feedrate}\n"  
                        # get set now that we've arrived at the corner
                        x, y, a = self._get_toolhead_in_position([point, points[index+1]])
                        a_machine_units = a / 360.0  # Convert degrees to machine units (1 inch = 360 degrees)
                        shape_toolpath += (
                            f"G0 Z{self.safe_height_z} ; Raise Z to rotate\n"
                            f"G0 X{x} Y{y} A{a_machine_units} ; Move to next segment start (corner)\n"
                            f"G0 Z{self.cut_height_z} ; Plunge to cutting height\n"
                        )
                    else:
                        x, y = self._calculate_next_xy([point, points[index+1]])
                        shape_toolpath += f"G1 X{x} Y{y} F{self.feedrate}\n"  
        return shape_toolpath
            
    def _shuffle_points(self, points: List[Tuple[float, float]], starting_point: int) -> List[Tuple[float, float]]:
        """
        Takes in a list of points and an index and shuffles the points
        so the passed index becomes the first point in the list, and
        the points preceding it get moved to the end of the list.
        """
        n = len(points)
        idx = starting_point % n  # handle negatives and out-of-range
        return points[idx:] + points[:idx]

    def _calculate_next_xy(self, segment: List[Tuple[float, float]]) -> Tuple[float, float]:
        """
        Return the point that is self.drag_offset (e.g., 0.5") **past P1**
        along the line from P0 to P1.

        segment: [P0, P1] where Pk = (x, y)
        """
        if len(segment) != 2:
            raise ValueError("segment must contain exactly two points")
        (x0, y0), (x1, y1) = segment

        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L < 1e-10:
            # Degenerate segment; no direction to go past P1
            return x1, y1

        ux, uy = dx / L, dy / L
        d = self.drag_offset  # expected to be 0.5"
        return x1 + d * ux, y1 + d * uy

    def _get_toolhead_in_position(self, segment: List[Tuple[float, float]]) -> Tuple[float, float, float]:
        """
        Gets toolhead in position for start of shape path or at corners. 
        Given two points [P0, P1], returns (X, Y, Adeg) where (X, Y) is 0.5" from P0 toward P1,
        and Adeg is the segment angle relative to +Y (Y = 0°), normalized to (-180, 180].
        """
        if len(segment) != 2:
            raise ValueError("segment must contain exactly two points")
        (x0, y0), (x1, y1) = segment
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L < 1e-10:
            # For zero-length segments, just return the first point with 0 angle
            return x0, y0, 0.0

        ux, uy = dx / L, dy / L
        x = x0 + self.drag_offset * ux
        y = y0 + self.drag_offset * uy

        # Angle from +X (CCW) then convert so +Y = 0°
        angle_x = math.degrees(math.atan2(dy, dx))
        a = 90.0 - angle_x
        a = ((a + 180.0) % 360.0) - 180.0  # normalize to (-180, 180]

        return x, y, a

    def _find_corners(self, points: List[Tuple[float, float]]) -> List[Tuple[int, Tuple[float, float]]]:
        """Finds all corners in a set of points."""
        corners = []
        for index, point in enumerate(points):
            if index == 0: # first point
                angle = self._angle_three_points(p0=points[-1], p1=points[index], p2=points[index+1])
            elif index == (len(points)-1): # last point
                angle = self._angle_three_points(p0=points[index-1], p1=points[index], p2=points[0])
            else: # all other points
                angle = self._angle_three_points(p0=points[index-1], p1=points[index], p2=points[index+1])
            print(angle)
            if abs(angle) >= self.corner_threshold:
                corners.append((index, point))
        return corners

    def _angle_three_points(
            self, p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float]
        ) -> float:
        """Return the (0..180] angle at p1 between segments p0->p1 and p1->p2, in degrees."""
        v1x, v1y = p1[0] - p0[0], p1[1] - p0[1]
        v2x, v2y = p2[0] - p1[0], p2[1] - p1[1]
        
        # Check for zero-length segments (with small tolerance)
        v1_len = math.sqrt(v1x*v1x + v1y*v1y)
        v2_len = math.sqrt(v2x*v2x + v2y*v2y)
        
        if v1_len < 1e-10 or v2_len < 1e-10:
            return 0.0  # No meaningful angle change for zero-length segments
            
        return math.degrees(math.atan2(v1x*v2y - v1y*v2x, v1x*v2x + v1y*v2y))

    def _save_points_to_csv(self, point_dictionary: Dict[str, List[Tuple[float, float]]]):
        """Save the points from DXF processor to a CSV file for inspection."""
        # Create output filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"dxf_points_{timestamp}.csv"
        csv_path = os.path.join(os.getcwd(), csv_filename)
        
        try:
            with open(csv_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['shape_name', 'point_index', 'x', 'y'])
                
                # Write all points from all shapes
                for shape_name, points in point_dictionary.items():
                    for point_index, (x, y) in enumerate(points):
                        writer.writerow([shape_name, point_index, f"{x:.6f}", f"{y:.6f}"])
            
            print(f"DXF points saved to: {csv_path}")
            
        except Exception as e:
            print(f"Warning: Could not save points to CSV: {e}")

