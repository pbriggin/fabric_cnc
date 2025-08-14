#!/usr/bin/env python3
"""
Drag Knife Toolpath Generator for grblHAL

Generates G-code for drag knife cutting with active A-axis control only at corners.
Between corners, the blade follows passively with no A commands.
"""

from typing import Dict, List, Tuple, Optional
import math

class ToolpathGenerator():
    """Main class for generating toolpaths."""

    def __init__(self):
        """Init function."""
        self.corner_threshold = 15.0 # degrees
        self.drag_offset = 0.5 # inches
        self.toolpath = ""
        self.safe_height_z = 0.0 # inches
        self.cut_height_z = -0.5
        self.feedrate = 6000

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
        if len(corners) == 0: # if there are no corners
            for index, point in enumerate(points):
                if index == 0: # if just starting out
                    x, y, a = self._get_toolhead_in_position([point, points[index+1]])
                    shape_toolpath += (
                        f"G0 X{x} Y{y} A{a} ; Move to start\n"
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
            for index, point in enumerate(points):
                if index == 0: # if just starting out or if at corner
                    x, y, a = self._get_toolhead_in_position([point, points[index+1]])
                    shape_toolpath += (
                        f"G0 X{x} Y{y} A{a} ; Move to start\n"
                        f"G0 Z{self.cut_height_z} ; Plunge to cutting height\n"
                    )
                elif index == (len(points)-1): # last point in path
                    x, y = self._calculate_next_xy([point, points[0]])
                    shape_toolpath += f"G1 X{x} Y{y} F{self.feedrate}\n" 
                else: # all other points
                    if any(corner[0] == index for corner in corners):
                        x, y, a = self._get_toolhead_in_position([point, points[index+1]])
                        shape_toolpath += (
                            f"G0 Z{self.safe_height_z} ; Raise Z to rotate\n"
                            f"G0 X{x} Y{y} A{a} ; Move to next segment start (corner)\n"
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
        """Calculates where XY should go for the current segment.
        Given two points [P0, P1], returns (X, Y) that is 0.5" from P0 toward P1.
        """
        if len(segment) != 2:
            raise ValueError("segment must contain exactly two points")
        (x0, y0), (x1, y1) = segment
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L == 0:
            raise ValueError("segment points must not be identical")

        ux, uy = dx / L, dy / L
        return x0 + self.drag_offset * ux, y0 + self.drag_offset * uy

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
        if L == 0:
            raise ValueError("segment points must not be identical")

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
            if abs(angle) >= self.corner_threshold:
                corners.append((index, point))
        return corners

    def _angle_three_points(
            self, p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float]
        ) -> float:
        """Return the (0..180] angle at p1 between segments p0->p1 and p1->p2, in degrees."""
        v1x, v1y = p1[0] - p0[0], p1[1] - p0[1]
        v2x, v2y = p2[0] - p1[0], p2[1] - p1[1]
        if (v1x == 0 and v1y == 0) or (v2x == 0 and v2y == 0):
            raise ValueError("Segments must have non-zero length")
        return math.degrees(math.atan2(v1x*v2y - v1y*v2x, v1x*v2x + v1y*v2y))

