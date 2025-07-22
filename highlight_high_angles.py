import matplotlib.pyplot as plt
import numpy as np
import math
from dxf_processor import DXFProcessor

def calculate_angle_change(p1, p2, p3):
    """Calculate the angle change between three consecutive points."""
    # Vector from p1 to p2
    v1_x = p2[0] - p1[0]
    v1_y = p2[1] - p1[1]
    
    # Vector from p2 to p3
    v2_x = p3[0] - p2[0]
    v2_y = p3[1] - p2[1]
    
    # Calculate dot product
    dot_product = v1_x * v2_x + v1_y * v2_y
    
    # Calculate magnitudes
    mag1 = math.sqrt(v1_x**2 + v1_y**2)
    mag2 = math.sqrt(v2_x**2 + v2_y**2)
    
    # Avoid division by zero
    if mag1 == 0 or mag2 == 0:
        return 0
    
    # Calculate cosine of angle
    cos_angle = dot_product / (mag1 * mag2)
    
    # Clamp to valid range for acos
    cos_angle = max(-1, min(1, cos_angle))
    
    # Calculate angle in radians
    angle_rad = math.acos(cos_angle)
    
    # Convert to degrees
    angle_deg = math.degrees(angle_rad)
    
    return angle_deg

def highlight_high_angles():
    """Plot DXF shapes and highlight segments with high angle changes."""
    dxf_path = "/Users/peterbriggs/Downloads/test_shapes.dxf"
    
    # Process the DXF file
    processor = DXFProcessor()
    shapes = processor.process_dxf(dxf_path)
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(15, 12))
    
    # Colors for different angle ranges
    colors = {
        'low': 'blue',      # 0-0.1°
        'medium': 'green',  # 0.1-1°
        'high': 'orange',   # 1-5°
        'very_high': 'red'  # >5°
    }
    
    # Track the highest angle segments for annotation
    highest_segments = []
    
    for shape_name, points in shapes.items():
        if len(points) < 3:
            continue
        
        # Convert points to numpy arrays for easier handling
        points_array = np.array(points)
        x_coords = points_array[:, 0]
        y_coords = points_array[:, 1]
        
        # Plot the shape with different colors based on angle changes
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            
            # Calculate angle change if we have 3 points
            if i > 0 and i < len(points) - 1:
                p0 = points[i - 1]
                angle_change = calculate_angle_change(p0, p1, p2)
                
                # Determine color based on angle
                if angle_change <= 0.1:
                    color = colors['low']
                elif angle_change <= 1.0:
                    color = colors['medium']
                elif angle_change <= 5.0:
                    color = colors['high']
                else:
                    color = colors['very_high']
                    # Track high angle segments
                    highest_segments.append({
                        'shape': shape_name,
                        'angle': angle_change,
                        'points': (p0, p1, p2),
                        'segment': (p1, p2)
                    })
            else:
                color = colors['low']  # Default for first/last segments
            
            # Plot the segment
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linewidth=1, alpha=0.7)
    
    # Sort highest segments by angle
    highest_segments.sort(key=lambda x: x['angle'], reverse=True)
    
    # Highlight the top 10 highest angle segments
    print("=== TOP 10 HIGHEST ANGLE SEGMENTS ===")
    for i, segment in enumerate(highest_segments[:10]):
        p1, p2 = segment['segment']
        angle = segment['angle']
        shape = segment['shape']
        
        print(f"{i+1}. {shape}: {angle:.3f}° at ({p1[0]:.3f}, {p1[1]:.3f}) -> ({p2[0]:.3f}, {p2[1]:.3f})")
        
        # Highlight on plot with thick red line and annotation
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='red', linewidth=4, alpha=0.8)
        ax.annotate(f"{angle:.1f}°", 
                   xy=((p1[0] + p2[0])/2, (p1[1] + p2[1])/2),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=8, color='red', weight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    
    # Set up the plot
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_title('DXF Shapes with Angle Change Highlighting\nRed = High angles (>5°), Orange = Medium (1-5°), Green = Low (0.1-1°), Blue = Very Low (≤0.1°)')
    
    # Add legend
    legend_elements = [
        plt.Line2D([0], [0], color=colors['low'], label='≤0.1° (Very Smooth)'),
        plt.Line2D([0], [0], color=colors['medium'], label='0.1-1° (Smooth)'),
        plt.Line2D([0], [0], color=colors['high'], label='1-5° (Moderate)'),
        plt.Line2D([0], [0], color=colors['very_high'], label='>5° (High)'),
        plt.Line2D([0], [0], color='red', linewidth=4, label='Top 10 Highest (Highlighted)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    # Save the plot
    plt.tight_layout()
    plt.savefig('dxf_angle_highlights.png', dpi=300, bbox_inches='tight')
    print(f"\nPlot saved as dxf_angle_highlights.png")
    
    # Show the plot
    plt.show()

if __name__ == "__main__":
    highlight_high_angles() 