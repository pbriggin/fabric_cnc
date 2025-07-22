#!/usr/bin/env python3
"""
Enhanced 2D GCODE Visualizer for Fabric CNC

Advanced visualization with:
- Tool path with Z-height color coding
- Tool orientation arrows showing A-axis rotation
- Corner detection and analysis
- Z-height change tracking
- Feed rate analysis
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import re
from typing import List, Tuple, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedGCodeVisualizer:
    """
    Enhanced GCODE visualizer with detailed tool orientation and analysis.
    """
    
    def __init__(self):
        self.x_positions = []
        self.y_positions = []
        self.z_positions = []
        self.a_positions = []
        self.feed_rates = []
        self.commands = []
        self.corner_points = []
        self.z_changes = []
        self.segments = []  # Store segment information
        
        # Current position
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_a = 0.0
        
        # Movement state
        self.last_z = 0.0
        self.segment_start = 0
        
    def parse_gcode_file(self, filename: str):
        """Parse a GCODE file and extract movement data."""
        logger.info(f"Parsing GCODE file: {filename}")
        
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
                
            self._parse_gcode_line(line, line_num)
    
    def _parse_gcode_line(self, line: str, line_num: int):
        """Parse a single GCODE line."""
        # Extract coordinates using regex
        x_match = re.search(r'X([-\d.]+)', line)
        y_match = re.search(r'Y([-\d.]+)', line)
        z_match = re.search(r'Z([-\d.]+)', line)
        a_match = re.search(r'A([-\d.]+)', line)
        f_match = re.search(r'F([-\d.]+)', line)
        
        # Update current position if coordinates found
        if x_match:
            self.current_x = float(x_match.group(1))
        if y_match:
            self.current_y = float(y_match.group(1))
        if z_match:
            self.current_z = float(z_match.group(1))
        if a_match:
            self.current_a = float(a_match.group(1))
        
        # Check if this is a movement command
        if line.startswith('G0') or line.startswith('G1'):
            self._record_movement(line, f_match.group(1) if f_match else None)
        
        # Check for corner handling
        if 'Raise Z for corner' in line:
            self.corner_points.append((self.current_x, self.current_y, line_num))
        
        # Check for Z changes
        if z_match and abs(self.current_z - self.last_z) > 0.1:
            self.z_changes.append((self.current_x, self.current_y, self.current_z, line_num))
            self.last_z = self.current_z
    
    def _record_movement(self, line: str, feed_rate: Optional[str]):
        """Record a movement command."""
        self.x_positions.append(self.current_x)
        self.y_positions.append(self.current_y)
        self.z_positions.append(self.current_z)
        self.a_positions.append(self.current_a)
        self.feed_rates.append(float(feed_rate) if feed_rate else 0.0)
        self.commands.append(line)
    
    def create_enhanced_visualization(self, output_filename: Optional[str] = None):
        """Create an enhanced 2D visualization."""
        if not self.x_positions:
            logger.warning("No movement data found to visualize")
            return
        
        # Create figure with multiple subplots
        fig = plt.figure(figsize=(20, 12))
        
        # Create grid layout
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
        
        # Convert to numpy arrays
        x_array = np.array(self.x_positions)
        y_array = np.array(self.y_positions)
        z_array = np.array(self.z_positions)
        a_array = np.array(self.a_positions)
        f_array = np.array(self.feed_rates)
        
        # Plot 1: Tool path with Z-height color coding
        ax1 = fig.add_subplot(gs[0, 0])
        self._plot_tool_path_z(ax1, x_array, y_array, z_array)
        
        # Plot 2: Tool orientation with A-axis arrows
        ax2 = fig.add_subplot(gs[0, 1])
        self._plot_tool_orientation_a(ax2, x_array, y_array, a_array)
        
        # Plot 3: Feed rate analysis
        ax3 = fig.add_subplot(gs[0, 2])
        self._plot_feed_rate_analysis(ax3, f_array)
        
        # Plot 4: Z-height over time
        ax4 = fig.add_subplot(gs[1, 0])
        self._plot_z_height_timeline(ax4, z_array)
        
        # Plot 5: A-axis rotation over time
        ax5 = fig.add_subplot(gs[1, 1])
        self._plot_a_rotation_timeline(ax5, a_array)
        
        # Plot 6: Corner analysis
        ax6 = fig.add_subplot(gs[1, 2])
        self._plot_corner_analysis(ax6, x_array, y_array)
        
        # Add corner markers to relevant plots
        if self.corner_points:
            corner_x = [p[0] for p in self.corner_points]
            corner_y = [p[1] for p in self.corner_points]
            ax1.scatter(corner_x, corner_y, c='red', s=100, marker='*', 
                       label=f'Corners ({len(self.corner_points)})', zorder=5)
            ax2.scatter(corner_x, corner_y, c='red', s=100, marker='*', 
                       label=f'Corners ({len(self.corner_points)})', zorder=5)
            ax6.scatter(corner_x, corner_y, c='red', s=100, marker='*', 
                       label=f'Corners ({len(self.corner_points)})', zorder=5)
        
        # Add Z-change markers
        if self.z_changes:
            z_change_x = [p[0] for p in self.z_changes]
            z_change_y = [p[1] for p in self.z_changes]
            z_change_z = [p[2] for p in self.z_changes]
            
            colors = ['green' if z > 0 else 'orange' for z in z_change_z]
            ax1.scatter(z_change_x, z_change_y, c=colors, s=50, marker='o', 
                       label=f'Z Changes ({len(self.z_changes)})', zorder=4)
            ax2.scatter(z_change_x, z_change_y, c=colors, s=50, marker='o', 
                       label=f'Z Changes ({len(self.z_changes)})', zorder=4)
        
        # Add legends
        ax1.legend()
        ax2.legend()
        ax6.legend()
        
        # Set titles
        ax1.set_title('Tool Path with Z-Height Color Coding')
        ax2.set_title('Tool Orientation (A-Axis)')
        ax3.set_title('Feed Rate Analysis')
        ax4.set_title('Z-Height Over Time')
        ax5.set_title('A-Axis Rotation Over Time')
        ax6.set_title('Corner Analysis')
        
        # Make axes equal for spatial plots
        ax1.set_aspect('equal')
        ax2.set_aspect('equal')
        ax6.set_aspect('equal')
        
        plt.tight_layout()
        
        # Save or show
        if output_filename:
            plt.savefig(output_filename, dpi=300, bbox_inches='tight')
            logger.info(f"Enhanced visualization saved to: {output_filename}")
        else:
            plt.show()
    
    def _plot_tool_path_z(self, ax, x_array, y_array, z_array):
        """Plot tool path with Z-height color coding."""
        # Create color map based on Z height
        z_min, z_max = z_array.min(), z_array.max()
        z_normalized = (z_array - z_min) / (z_max - z_min) if z_max > z_min else np.zeros_like(z_array)
        
        # Create color map (blue for low Z, red for high Z)
        colors = plt.cm.coolwarm(z_normalized)
        
        # Plot the path with color coding
        for i in range(len(x_array) - 1):
            ax.plot([x_array[i], x_array[i+1]], [y_array[i], y_array[i+1]], 
                   color=colors[i], linewidth=2, alpha=0.8)
        
        # Add start and end markers
        ax.scatter(x_array[0], y_array[0], c='green', s=100, marker='o', 
                  label='Start', zorder=5)
        ax.scatter(x_array[-1], y_array[-1], c='red', s=100, marker='s', 
                  label='End', zorder=5)
        
        # Add colorbar
        sm = plt.cm.ScalarMappable(cmap=plt.cm.coolwarm, 
                                  norm=plt.Normalize(vmin=z_min, vmax=z_max))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label('Z Height (mm)')
        
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.grid(True, alpha=0.3)
    
    def _plot_tool_orientation_a(self, ax, x_array, y_array, a_array):
        """Plot tool orientation with A-axis direction arrows."""
        # Plot the path
        ax.plot(x_array, y_array, 'b-', linewidth=1, alpha=0.5, label='Tool Path')
        
        # Add orientation arrows at regular intervals
        step = max(1, len(x_array) // 30)  # Show ~30 arrows
        for i in range(0, len(x_array), step):
            if i < len(x_array) - 1:
                # Calculate direction vector based on A-axis rotation
                angle_rad = np.radians(a_array[i])
                dx = np.cos(angle_rad)
                dy = np.sin(angle_rad)
                
                # Scale arrow
                arrow_length = 3.0
                
                # Draw arrow
                ax.arrow(x_array[i], y_array[i], 
                        dx * arrow_length, dy * arrow_length,
                        head_width=1.0, head_length=1.0, 
                        fc='blue', ec='blue', alpha=0.7)
        
        # Add start and end markers
        ax.scatter(x_array[0], y_array[0], c='green', s=100, marker='o', 
                  label='Start', zorder=5)
        ax.scatter(x_array[-1], y_array[-1], c='red', s=100, marker='s', 
                  label='End', zorder=5)
        
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.grid(True, alpha=0.3)
    
    def _plot_feed_rate_analysis(self, ax, f_array):
        """Plot feed rate analysis."""
        # Filter out zero feed rates
        non_zero_f = f_array[f_array > 0]
        
        if len(non_zero_f) > 0:
            ax.hist(non_zero_f, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax.axvline(non_zero_f.mean(), color='red', linestyle='--', 
                      label=f'Mean: {non_zero_f.mean():.1f} mm/min')
            ax.axvline(non_zero_f.max(), color='orange', linestyle='--', 
                      label=f'Max: {non_zero_f.max():.1f} mm/min')
            ax.legend()
        
        ax.set_xlabel('Feed Rate (mm/min)')
        ax.set_ylabel('Frequency')
        ax.set_title('Feed Rate Distribution')
        ax.grid(True, alpha=0.3)
    
    def _plot_z_height_timeline(self, ax, z_array):
        """Plot Z-height over time."""
        ax.plot(range(len(z_array)), z_array, 'b-', linewidth=1)
        ax.set_xlabel('Movement Index')
        ax.set_ylabel('Z Height (mm)')
        ax.grid(True, alpha=0.3)
        
        # Highlight Z changes
        if self.z_changes:
            change_indices = [i for i, (_, _, _, _) in enumerate(self.z_changes)]
            change_heights = [z for _, _, z, _ in self.z_changes]
            ax.scatter(change_indices, change_heights, c='red', s=50, alpha=0.7)
    
    def _plot_a_rotation_timeline(self, ax, a_array):
        """Plot A-axis rotation over time."""
        ax.plot(range(len(a_array)), a_array, 'g-', linewidth=1)
        ax.set_xlabel('Movement Index')
        ax.set_ylabel('A-Axis Rotation (degrees)')
        ax.grid(True, alpha=0.3)
        
        # Highlight corner rotations
        if self.corner_points:
            corner_indices = [i for i, (_, _, _) in enumerate(self.corner_points)]
            corner_angles = [a_array[i] for i in corner_indices if i < len(a_array)]
            ax.scatter(corner_indices[:len(corner_angles)], corner_angles, c='red', s=50, alpha=0.7)
    
    def _plot_corner_analysis(self, ax, x_array, y_array):
        """Plot corner analysis."""
        # Plot the full path
        ax.plot(x_array, y_array, 'b-', linewidth=1, alpha=0.5, label='Tool Path')
        
        # Highlight corners with larger markers
        if self.corner_points:
            corner_x = [p[0] for p in self.corner_points]
            corner_y = [p[1] for p in self.corner_points]
            ax.scatter(corner_x, corner_y, c='red', s=150, marker='*', 
                      label=f'Corners ({len(self.corner_points)})', zorder=5)
        
        # Add start and end markers
        ax.scatter(x_array[0], y_array[0], c='green', s=100, marker='o', 
                  label='Start', zorder=5)
        ax.scatter(x_array[-1], y_array[-1], c='red', s=100, marker='s', 
                  label='End', zorder=5)
        
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.grid(True, alpha=0.3)
    
    def print_detailed_statistics(self):
        """Print detailed statistics about the GCODE file."""
        if not self.x_positions:
            print("No data to analyze")
            return
        
        print("\n=== Enhanced GCODE Analysis ===")
        print(f"Total movements: {len(self.x_positions)}")
        print(f"Corners detected: {len(self.corner_points)}")
        print(f"Z-height changes: {len(self.z_changes)}")
        
        if self.x_positions:
            x_array = np.array(self.x_positions)
            y_array = np.array(self.y_positions)
            z_array = np.array(self.z_positions)
            a_array = np.array(self.a_positions)
            f_array = np.array(self.feed_rates)
            
            print(f"\nSpatial Range:")
            print(f"  X: {x_array.min():.2f} to {x_array.max():.2f} mm")
            print(f"  Y: {y_array.min():.2f} to {y_array.max():.2f} mm")
            print(f"  Z: {z_array.min():.2f} to {z_array.max():.2f} mm")
            print(f"  A: {a_array.min():.2f} to {a_array.max():.2f} degrees")
            
            # Calculate total path length
            total_length = 0
            for i in range(len(x_array) - 1):
                dx = x_array[i+1] - x_array[i]
                dy = y_array[i+1] - y_array[i]
                total_length += np.sqrt(dx**2 + dy**2)
            
            print(f"\nPath Statistics:")
            print(f"  Total path length: {total_length:.2f} mm")
            print(f"  Average segment length: {total_length/(len(x_array)-1):.2f} mm")
            
            # Feed rate analysis
            non_zero_f = f_array[f_array > 0]
            if len(non_zero_f) > 0:
                print(f"\nFeed Rate Analysis:")
                print(f"  Average feed rate: {non_zero_f.mean():.1f} mm/min")
                print(f"  Maximum feed rate: {non_zero_f.max():.1f} mm/min")
                print(f"  Minimum feed rate: {non_zero_f.min():.1f} mm/min")
            
            # Corner analysis
            if self.corner_points:
                print(f"\nCorner Analysis:")
                print(f"  Corner frequency: {len(self.corner_points)/total_length*1000:.2f} corners/meter")
                print(f"  Average distance between corners: {total_length/len(self.corner_points):.2f} mm")


def main():
    """Test the enhanced GCODE visualizer."""
    visualizer = EnhancedGCodeVisualizer()
    
    # Parse the GCODE file
    gcode_file = "toolpath_test_2.gcode"
    
    try:
        print(f"Analyzing GCODE file: {gcode_file}")
        visualizer.parse_gcode_file(gcode_file)
        
        # Print detailed statistics
        visualizer.print_detailed_statistics()
        
        # Create enhanced visualization
        output_file = "enhanced_gcode_visualization.png"
        visualizer.create_enhanced_visualization(output_file)
        
        print(f"\nEnhanced visualization saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 