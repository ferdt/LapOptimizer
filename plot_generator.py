import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import io

def generate_track_plot(vehicle_name, track_name, run_data, track_coords, dpi=150):
    """
    Generate a high-quality matplotlib plot showing track layout with velocity-colored trajectory
    and speed profile.
    
    Args:
        vehicle_name: Name of the vehicle
        track_name: Name of the track
        run_data: Dictionary containing simulation results (x, y, u, s, time)
        track_coords: Dictionary with track coordinates (center, left, right)
        dpi: Resolution for the output image
        
    Returns:
        BytesIO object containing the PNG image
    """
    # Extract data
    t = np.array(run_data['time'])
    x = np.array(run_data['x'])
    y = np.array(run_data['y'])
    u = np.array(run_data['u'])  # Already in km/h
    d = np.array(run_data['s'])
    
    # Calculate laptime
    laptime = max(t)
    laptime_str = f"{int(laptime // 60)}:{int(laptime % 60):02d}.{int((laptime % 1) * 1000 // 10):02d}"
    
    # Configure HD figure
    width_px = 1920 * 2
    height_px = 1080 * 2
    figsize = (width_px / dpi, height_px / dpi)
    
    fig, (ax1, ax2) = plt.subplots(
        2, 1, 
        figsize=figsize, 
        dpi=dpi, 
        gridspec_kw={'height_ratios': [2, 1]}
    )
    
    # --- Top plot: Track with velocity-colored trajectory ---
    
    # Create line segments
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Create LineCollection with colormap based on velocity
    lc = LineCollection(segments, cmap='jet', linewidth=2)
    lc.set_array(u)
    ax1.add_collection(lc)
    
    # Plot track boundaries if available (plot BEFORE trajectory so it's underneath)
    if track_coords:
        x_center = track_coords.get('x_center', [])
        y_center = track_coords.get('y_center', [])
        x_left = track_coords.get('x_left', [])
        y_left = track_coords.get('y_left', [])
        x_right = track_coords.get('x_right', [])
        y_right = track_coords.get('y_right', [])
        
        # Plot track boundaries with improved visibility
        if x_left and y_left:
            ax1.plot(
                x_left, y_left, 
                linewidth=2,
                color='black',
                linestyle='-',
                alpha=0.7,
                label='Track Limits'
            )
        if x_right and y_right:
            ax1.plot(
                x_right, y_right, 
                linewidth=2,
                color='black',
                linestyle='-',
                alpha=0.7
            )
        if x_center and y_center:
            ax1.plot(
                x_center, y_center, 
                linewidth=1, 
                color=(0.537, 0.604, 0.722, 1.0), 
                linestyle=(0, (20, 4)),
                alpha=0.5
            )
    
    # Create line segments for trajectory
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Create LineCollection with colormap based on velocity
    lc = LineCollection(segments, cmap='jet', linewidth=3, zorder=10)  # zorder to put on top
    lc.set_array(u)
    ax1.add_collection(lc)
    
    
    # Set axis limits explicitly (LineCollection doesn't auto-update limits)
    # Add padding to ensure track boundaries are visible
    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()
    
    x_range = x_max - x_min
    y_range = y_max - y_min
    padding = 0.05  # 5% padding
    
    ax1.set_xlim(x_min - x_range * padding, x_max + x_range * padding)
    ax1.set_ylim(y_min - y_range * padding, y_max + y_range * padding)
    
    ax1.set_title(f"{track_name} - {vehicle_name} - {laptime_str}")
    ax1.set_aspect('equal')
    ax1.invert_yaxis()
    
    # Add colorbar
    cbar = plt.colorbar(lc, ax=ax1, orientation='vertical')
    cbar.set_label("Velocidad [km/h]")
    
    # --- Bottom plot: Speed profile ---
    ax2.plot(d, u, color="orange")
    ax2.set_ylabel("Velocidad [km/h]")
    ax2.set_xlabel("Distancia [m]")
    ax2.grid()
    
    plt.tight_layout()
    
    # Save to BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi)
    buf.seek(0)
    plt.close(fig)
    
    return buf


def generate_track_plot_file(vehicle_name, track_name, run_data, track_coords, output_path, dpi=150):
    """
    Save track plot directly to file.
    
    Args:
        vehicle_name: Name of the vehicle
        track_name: Name of the track
        run_data: Dictionary containing simulation results
        track_coords: Dictionary with track coordinates
        output_path: Path where to save the image
        dpi: Resolution for the output image
    """
    buf = generate_track_plot(vehicle_name, track_name, run_data, track_coords, dpi)
    
    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())
    
    print(f"Plot saved to {output_path}")
