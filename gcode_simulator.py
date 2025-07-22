#!/usr/bin/env python3
"""
GCODE Simulator for Fabric CNC

Simulates and visualizes GCODE execution with:
- Real-time toolpath animation
- 3D visualization of X, Y, Z, and A (rotation) movements
- Corner detection highlighting
- Feed rate simulation
"""

import re
import time
import math
import logging
from typing import List, Tuple, Optional, Dict
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCodeSimulator:
    """
    Simulates GCODE execution with 3D visualization.
    """
    
    def __init__(self, gcode_file: str):
        """
        Initialize the GCODE simulator.
        
        Args:
            gcode_file: Path to the GCODE file to simulate
        """
        self.gcode_file = gcode_file
        self.gcode_lines = []
        self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
        self.toolpath_points = []
        self.corner_points = []
        self.feed_rates = []
        self.timestamps = []
        
        # Simulation parameters
        self.simulation_speed = 1.0  # Speed multiplier
        self.max_feed_rate = 1000.0  # mm/min
        
    def load_gcode(self) -> bool:
        """
        Load and parse GCODE file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.gcode_file, 'r') as f:
                self.gcode_lines = f.readlines()
            
            logger.info(f"Loaded {len(self.gcode_lines)} GCODE lines")
            return True
            
        except Exception as e:
            logger.error(f"Error loading GCODE file: {e}")
            return False
    
    def parse_gcode_line(self, line: str) -> Dict:
        """
        Parse a single GCODE line and extract commands.
        
        Args:
            line: GCODE line to parse
            
        Returns:
            Dictionary with parsed commands
        """
        # Remove comments and whitespace
        line = re.sub(r';.*$', '', line).strip()
        if not line:
            return {}
        
        # Parse GCODE commands
        commands = {}
        
        # G0/G1 (rapid/linear move)
        g_match = re.search(r'G([01])', line)
        if g_match:
            commands['G'] = int(g_match.group(1))
        
        # X, Y, Z, A coordinates
        for axis in ['X', 'Y', 'Z', 'A']:
            match = re.search(f'{axis}([+-]?\\d*\\.?\\d+)', line)
            if match:
                commands[axis] = float(match.group(1))
        
        # F (feed rate)
        f_match = re.search(r'F([+-]?\\d*\\.?\\d+)', line)
        if f_match:
            commands['F'] = float(f_match.group(1))
        
        return commands
    
    def simulate_execution(self) -> bool:
        """
        Simulate GCODE execution and record toolpath.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting GCODE simulation...")
        
        # Initialize toolpath
        self.toolpath_points = [self.current_position.copy()]
        self.corner_points = []
        self.feed_rates = [0.0]
        self.timestamps = [0.0]
        
        current_time = 0.0
        
        for i, line in enumerate(self.gcode_lines):
            commands = self.parse_gcode_line(line)
            
            if not commands:
                continue
            
            # Handle movement commands
            if 'G' in commands:
                g_code = commands['G']
                
                # Calculate new position
                new_position = self.current_position.copy()
                for axis in ['X', 'Y', 'Z', 'A']:
                    if axis in commands:
                        new_position[axis] = commands[axis]
                
                # Calculate movement distance
                dx = new_position['X'] - self.current_position['X']
                dy = new_position['Y'] - self.current_position['Y']
                dz = new_position['Z'] - self.current_position['Z']
                distance = math.sqrt(dx*dx + dy*dy + dz*dz)
                
                # Determine feed rate
                if 'F' in commands:
                    feed_rate = commands['F']
                elif g_code == 0:  # G0 (rapid move)
                    feed_rate = self.max_feed_rate
                else:  # G1 (linear move)
                    feed_rate = self.max_feed_rate
                
                # Calculate movement time
                if distance > 0:
                    movement_time = (distance / feed_rate) * 60.0  # Convert to seconds
                else:
                    movement_time = 0.0
                
                # Update current position
                self.current_position = new_position
                
                # Record toolpath point
                self.toolpath_points.append(self.current_position.copy())
                self.feed_rates.append(feed_rate)
                current_time += movement_time
                self.timestamps.append(current_time)
                
                # Detect corners (Z raising)
                if len(self.toolpath_points) > 2:
                    prev_point = self.toolpath_points[-3]
                    curr_point = self.toolpath_points[-2]
                    next_point = self.toolpath_points[-1]
                    
                    # Check if Z was raised (indicates corner)
                    if abs(curr_point['Z'] - prev_point['Z']) > 0.1 and curr_point['Z'] > prev_point['Z']:
                        self.corner_points.append(len(self.toolpath_points) - 2)
        
        logger.info(f"Simulation complete: {len(self.toolpath_points)} toolpath points")
        logger.info(f"Detected {len(self.corner_points)} corners")
        logger.info(f"Total simulation time: {current_time:.2f} seconds")
        
        return True
    
    def create_3d_visualization(self, save_animation: bool = False):
        """
        Create 3D visualization of the toolpath.
        
        Args:
            save_animation: Whether to save the animation as a video file
        """
        if not self.toolpath_points:
            logger.error("No toolpath data available. Run simulation first.")
            return
        
        # Extract coordinates
        x_coords = [p['X'] for p in self.toolpath_points]
        y_coords = [p['Y'] for p in self.toolpath_points]
        z_coords = [p['Z'] for p in self.toolpath_points]
        a_coords = [p['A'] for p in self.toolpath_points]
        
        # Create figure
        fig = plt.figure(figsize=(15, 10))
        
        # 3D toolpath plot
        ax1 = fig.add_subplot(221, projection='3d')
        ax1.plot(x_coords, y_coords, z_coords, 'b-', linewidth=1, alpha=0.7, label='Toolpath')
        
        # Highlight corners
        if self.corner_points:
            corner_x = [x_coords[i] for i in self.corner_points]
            corner_y = [y_coords[i] for i in self.corner_points]
            corner_z = [z_coords[i] for i in self.corner_points]
            ax1.scatter(corner_x, corner_y, corner_z, c='red', s=50, label='Corners')
        
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel('Y (mm)')
        ax1.set_zlabel('Z (mm)')
        ax1.set_title('3D Toolpath')
        ax1.legend()
        
        # 2D XY projection
        ax2 = fig.add_subplot(222)
        ax2.plot(x_coords, y_coords, 'b-', linewidth=1, alpha=0.7)
        if self.corner_points:
            corner_x = [x_coords[i] for i in self.corner_points]
            corner_y = [y_coords[i] for i in self.corner_points]
            ax2.scatter(corner_x, corner_y, c='red', s=30)
        ax2.set_xlabel('X (mm)')
        ax2.set_ylabel('Y (mm)')
        ax2.set_title('XY Projection')
        ax2.axis('equal')
        
        # Z height over time
        ax3 = fig.add_subplot(223)
        ax3.plot(self.timestamps, z_coords, 'g-', linewidth=2)
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Z (mm)')
        ax3.set_title('Z Height vs Time')
        ax3.grid(True)
        
        # A rotation over time
        ax4 = fig.add_subplot(224)
        ax4.plot(self.timestamps, a_coords, 'm-', linewidth=2)
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('A (degrees)')
        ax4.set_title('A Rotation vs Time')
        ax4.grid(True)
        
        plt.tight_layout()
        
        # Save static plot
        plt.savefig(f'simulation_{self.gcode_file.replace(".gcode", "")}.png', dpi=300, bbox_inches='tight')
        logger.info(f"Static visualization saved as simulation_{self.gcode_file.replace('.gcode', '')}.png")
        
        if save_animation:
            self._create_animation(fig, ax1, ax2)
        
        plt.show()
    
    def _create_animation(self, fig, ax1, ax2):
        """
        Create animated visualization of toolpath execution.
        
        Args:
            fig: Matplotlib figure
            ax1: 3D subplot
            ax2: 2D subplot
        """
        logger.info("Creating animation...")
        
        # Extract coordinates
        x_coords = [p['X'] for p in self.toolpath_points]
        y_coords = [p['Y'] for p in self.toolpath_points]
        z_coords = [p['Z'] for p in self.toolpath_points]
        
        def animate(frame):
            # Clear previous positions
            ax1.clear()
            ax2.clear()
            
            # Plot toolpath up to current frame
            ax1.plot(x_coords[:frame+1], y_coords[:frame+1], z_coords[:frame+1], 'b-', linewidth=1, alpha=0.7)
            ax2.plot(x_coords[:frame+1], y_coords[:frame+1], 'b-', linewidth=1, alpha=0.7)
            
            # Show current position
            if frame < len(x_coords):
                ax1.scatter([x_coords[frame]], [y_coords[frame]], [z_coords[frame]], c='red', s=100)
                ax2.scatter([x_coords[frame]], [y_coords[frame]], c='red', s=100)
            
            # Set labels and titles
            ax1.set_xlabel('X (mm)')
            ax1.set_ylabel('Y (mm)')
            ax1.set_zlabel('Z (mm)')
            ax1.set_title(f'3D Toolpath (Frame {frame}/{len(x_coords)})')
            
            ax2.set_xlabel('X (mm)')
            ax2.set_ylabel('Y (mm)')
            ax2.set_title('XY Projection')
            ax2.axis('equal')
            
            return ax1, ax2
        
        # Create animation
        anim = animation.FuncAnimation(fig, animate, frames=len(x_coords), 
                                     interval=50, blit=False, repeat=True)
        
        # Save animation
        output_file = f'animation_{self.gcode_file.replace(".gcode", "")}.mp4'
        anim.save(output_file, writer='ffmpeg', fps=20)
        logger.info(f"Animation saved as {output_file}")
    
    def print_statistics(self):
        """Print simulation statistics."""
        if not self.toolpath_points:
            logger.error("No toolpath data available. Run simulation first.")
            return
        
        print("\n" + "="*50)
        print("GCODE SIMULATION STATISTICS")
        print("="*50)
        
        # Basic stats
        print(f"GCODE file: {self.gcode_file}")
        print(f"Total lines: {len(self.gcode_lines)}")
        print(f"Toolpath points: {len(self.toolpath_points)}")
        print(f"Corners detected: {len(self.corner_points)}")
        print(f"Total simulation time: {self.timestamps[-1]:.2f} seconds")
        
        # Coordinate ranges
        x_coords = [p['X'] for p in self.toolpath_points]
        y_coords = [p['Y'] for p in self.toolpath_points]
        z_coords = [p['Z'] for p in self.toolpath_points]
        a_coords = [p['A'] for p in self.toolpath_points]
        
        print(f"\nCoordinate Ranges:")
        print(f"X: {min(x_coords):.3f} to {max(x_coords):.3f} mm")
        print(f"Y: {min(y_coords):.3f} to {max(y_coords):.3f} mm")
        print(f"Z: {min(z_coords):.3f} to {max(z_coords):.3f} mm")
        print(f"A: {min(a_coords):.3f} to {max(a_coords):.3f} degrees")
        
        # Movement analysis
        total_distance = 0.0
        cutting_distance = 0.0
        rapid_distance = 0.0
        
        for i in range(1, len(self.toolpath_points)):
            prev = self.toolpath_points[i-1]
            curr = self.toolpath_points[i]
            
            dx = curr['X'] - prev['X']
            dy = curr['Y'] - prev['Y']
            dz = curr['Z'] - prev['Z']
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            total_distance += distance
            
            if curr['Z'] < 0:  # Cutting
                cutting_distance += distance
            else:  # Rapid move
                rapid_distance += distance
        
        print(f"\nMovement Analysis:")
        print(f"Total distance: {total_distance:.2f} mm")
        print(f"Cutting distance: {cutting_distance:.2f} mm")
        print(f"Rapid move distance: {rapid_distance:.2f} mm")
        print(f"Cutting percentage: {(cutting_distance/total_distance*100):.1f}%")
        
        # Corner analysis
        if self.corner_points:
            print(f"\nCorner Analysis:")
            print(f"Average corner spacing: {len(self.toolpath_points)/len(self.corner_points):.1f} points")
            
            corner_times = [self.timestamps[i] for i in self.corner_points]
            if len(corner_times) > 1:
                corner_intervals = [corner_times[i+1] - corner_times[i] for i in range(len(corner_times)-1)]
                print(f"Average time between corners: {np.mean(corner_intervals):.2f} seconds")
        
        print("="*50)


def main():
    """Main function to run the GCODE simulator."""
    # GCODE file to simulate
    gcode_file = "toolpath_test_2.gcode"
    
    # Create simulator
    simulator = GCodeSimulator(gcode_file)
    
    # Load GCODE
    if not simulator.load_gcode():
        print("Failed to load GCODE file")
        return
    
    # Run simulation
    if not simulator.simulate_execution():
        print("Failed to simulate GCODE execution")
        return
    
    # Print statistics
    simulator.print_statistics()
    
    # Create visualization
    print("\nCreating visualization...")
    simulator.create_3d_visualization(save_animation=False)  # Set to True to save animation


if __name__ == "__main__":
    main() 