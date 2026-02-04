import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import io

def rotate_points(x, y, angle_rad):
    """Rotate points around the origin (0,0) by a given angle."""
    x_rot = x * np.cos(angle_rad) - y * np.sin(angle_rad)
    y_rot = x * np.sin(angle_rad) + y * np.cos(angle_rad)
    return x_rot, y_rot

def calculate_best_fit_rotation(x, y):
    """
    Calculate the rotation angle that aligns the track's principal axis with the X-axis.
    Uses PCA (Principal Component Analysis).
    """
    # Center data
    x_c = x - np.mean(x)
    y_c = y - np.mean(y)
    coords = np.vstack([x_c, y_c])
    
    # Covariance matrix
    cov = np.cov(coords)
    
    # Eigenvalues and eigenvectors
    evals, evecs = np.linalg.eig(cov)
    
    # Get eigenvector corresponding to largest eigenvalue (principal component)
    pc1 = evecs[:, np.argmax(evals)]
    
    # Calculate angle
    angle = np.arctan2(pc1[1], pc1[0])
    
    # We want this axis to be horizontal (angle = 0), so we rotate by -angle
    return -angle

def get_start_finish_line(x_center, y_center, width=10.0):
    """
    Calculate coordinates for a line perpendicular to the track at the start (index 0).
    """
    if len(x_center) < 2:
        return None, None
        
    # Vector at start
    dx = x_center[1] - x_center[0]
    dy = y_center[1] - y_center[0]
    
    # Normalize
    length = np.sqrt(dx**2 + dy**2)
    if length == 0: return None, None
    dx /= length
    dy /= length
    
    # Perpendicular vector (-dy, dx)
    px = -dy
    py = dx
    
    # Line points
    x_sf = [x_center[0] - px * width/2, x_center[0] + px * width/2]
    y_sf = [y_center[0] - py * width/2, y_center[0] + py * width/2]
    
    return x_sf, y_sf

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
    # Extract data
    t = np.array(run_data['time'])
    x_orig = np.array(run_data['x'])
    y_orig = np.array(run_data['y'])
    u = np.array(run_data['u']) * 3.6  # Convert m/s to km/h
    d = np.array(run_data['s'])

    # Calculate rotation for best fit (using Centerline if available, else trajectory)
    if track_coords and track_coords.get('x_center'):
        rot_angle = calculate_best_fit_rotation(np.array(track_coords['x_center']), np.array(track_coords['y_center']))
    else:
        rot_angle = calculate_best_fit_rotation(x_orig, y_orig)

    # Rotate Trajectory
    x, y = rotate_points(x_orig, y_orig, rot_angle)
    
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
        
        # Rotate coordinates
        if x_left is not None and len(x_left) > 0 and y_left is not None and len(y_left) > 0:
             x_left, y_left = rotate_points(np.array(x_left), np.array(y_left), rot_angle)
        if x_right is not None and len(x_right) > 0 and y_right is not None and len(y_right) > 0:
             x_right, y_right = rotate_points(np.array(x_right), np.array(y_right), rot_angle)
        if x_center is not None and len(x_center) > 0 and y_center is not None and len(y_center) > 0:
             # Calculate Start/Finish line BEFORE rotation (vector math is easier) but rotate points
             # Actually easier to rotate geometry then calculate perp
             x_c_rot, y_c_rot = rotate_points(np.array(x_center), np.array(y_center), rot_angle)
             
             # Calculate SF line using rotated center
             x_sf, y_sf = get_start_finish_line(x_c_rot, y_c_rot, width=20.0) # 20m wide marker
             
             x_center, y_center = x_c_rot, y_c_rot # Update standard vars for plotting

        # Plot track boundaries with improved visibility
        if x_left is not None and len(x_left) > 0 and y_left is not None and len(y_left) > 0:
            ax1.plot(
                x_left, y_left, 
                linewidth=2,
                color='black',
                linestyle='-',
                alpha=0.7,
                label='Track Limits'
            )
        if x_right is not None and len(x_right) > 0 and y_right is not None and len(y_right) > 0:
            ax1.plot(
                x_right, y_right, 
                linewidth=2,
                color='black',
                linestyle='-',
                alpha=0.7
            )
        if x_center is not None and len(x_center) > 0 and y_center is not None and len(y_center) > 0:
            ax1.plot(
                x_center, y_center, 
                linewidth=1, 
                color=(0.537, 0.604, 0.722, 1.0), 
                linestyle=(0, (20, 4)),
                alpha=0.5,
                label='Centerline'
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
    
    # Add legend
    ax1.legend(loc='upper right', framealpha=0.9)
    
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


def generate_comparison_plot(track_name, results_dict, track_coords, dpi=150):
    """
    Generate a comparison plot showing multiple vehicles on the same track.
    
    Args:
        track_name: Name of the track
        results_dict: Dict mapping vehicle names to their run_data
        track_coords: Dictionary with track coordinates
        dpi: Resolution for the output image
        
    Returns:
        BytesIO object containing the PNG image
    """
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
    
    # Define colors for different vehicles
    import matplotlib.cm as cm
    colors = cm.tab10(np.linspace(0, 1, len(results_dict)))
    
    
    # Calculate global rotation based on first vehicle (or track if we extracted it above)
    rot_angle = 0
    if len(results_dict) > 0:
         first_res = list(results_dict.values())[0]
         rot_angle = calculate_best_fit_rotation(np.array(first_res['x']), np.array(first_res['y']))

    # Rotate Boundaries (we need to do this carefully if we already plotted them? No, we plotted above)
    # Wait, in the code above I plot boundaries BEFORE rotating. That's wrong.
    # I need to rotate boundaries first.
    
    ax1.clear() # Clear the axis to re-plot with rotation
    
    # Re-plot Rotated Boundaries
    x_sf, y_sf = None, None
    
    # 2. Plot Track Boundaries (Rotated)
    if track_coords:
        x_left = track_coords.get('x_left', [])
        y_left = track_coords.get('y_left', [])
        x_right = track_coords.get('x_right', [])
        y_right = track_coords.get('y_right', [])
        x_center = track_coords.get('x_center', [])
        y_center = track_coords.get('y_center', [])
        
        # Rotate and Plot Centerline + Start/Finish
        if x_center is not None and len(x_center) > 0 and y_center is not None and len(y_center) > 0:
             # Rotate
             x_c_rot, y_c_rot = rotate_points(np.array(x_center), np.array(y_center), rot_angle)
             
             # Calculate SF line
             x_sf, y_sf = get_start_finish_line(x_c_rot, y_c_rot, width=20.0)
             
             # Plot Centerline
             ax1.plot(x_c_rot, y_c_rot, linewidth=1, color=(0.537, 0.604, 0.722, 1.0), 
                    linestyle=(0, (20, 4)), alpha=0.3, label='Centerline')
             
             # Plot SF Line
             if x_sf and y_sf:
                 ax1.plot(x_sf, y_sf, linewidth=2, color='red', linestyle='-', zorder=20, label='Start/Finish')

        # Rotate and Plot Left/Right
        if x_left is not None and len(x_left) > 0 and y_left is not None and len(y_left) > 0:
            x_l, y_l = rotate_points(np.array(x_left), np.array(y_left), rot_angle)
            ax1.plot(x_l, y_l, linewidth=2, color='black', linestyle='-', alpha=0.3)
            
        if x_right is not None and len(x_right) > 0 and y_right is not None and len(y_right) > 0:
            x_r, y_r = rotate_points(np.array(x_right), np.array(y_right), rot_angle)
            ax1.plot(x_r, y_r, linewidth=2, color='black', linestyle='-', alpha=0.3)
    
    # 3. Plot each vehicle's trajectory (Rotated)
    all_x, all_y = [], []
    for idx, (vehicle_name, run_data) in enumerate(results_dict.items()):
        x_orig = np.array(run_data['x'])
        y_orig = np.array(run_data['y'])
        
        # Rotate
        x, y = rotate_points(x_orig, y_orig, rot_angle)
        
        u = np.array(run_data['u']) * 3.6  # Convert to km/h
        
        all_x.extend(x)
        all_y.extend(y)
        
        ax1.plot(x, y, linewidth=1, color=colors[idx], label=vehicle_name, alpha=0.8)
    
    # Set axis limits
    if all_x and all_y:
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        x_range = x_max - x_min
        y_range = y_max - y_min
        padding = 0.05
        ax1.set_xlim(x_min - x_range * padding, x_max + x_range * padding)
        ax1.set_ylim(y_min - y_range * padding, y_max + y_range * padding)
    
    ax1.set_title(f"{track_name} - Vehicle Comparison")
    ax1.set_aspect('equal')
    ax1.invert_yaxis()
    ax1.legend(loc='upper right', framealpha=0.9)
    
    # --- Bottom plot: Speed comparison ---
    for idx, (vehicle_name, run_data) in enumerate(results_dict.items()):
        d = np.array(run_data['s'])
        u = np.array(run_data['u']) * 3.6  # Convert to km/h
        ax2.plot(d, u, linewidth=2, color=colors[idx], label=vehicle_name, alpha=0.8)
    
    ax2.set_ylabel("Velocidad [km/h]")
    ax2.set_xlabel("Distancia [m]")
    ax2.grid(alpha=0.3)
    ax2.legend(loc='best', framealpha=0.9)
    
    plt.tight_layout()
    
    # Save to BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi)
    buf.seek(0)
    plt.close(fig)
    
    return buf
