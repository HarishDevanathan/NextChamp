# =========================
# 📌 Setup
# =========================
import cv2
import numpy as np
import matplotlib.pyplot as plt
from ultralytics import YOLO
from scipy.signal import find_peaks, savgol_filter

# =========================
# 📌 Load YOLOv8 Pose Model
# =========================
model = YOLO("yolov8n-pose.pt")  # lightweight pose model

# =========================
# 📌 Improved Jump Height Calculation Methods
# =========================

def calculate_jump_height_improved(hip_y_values, knee_y_values, ankle_y_values, fps, method="multi_point"):
    """
    Improved jump height calculation with multiple methods
    
    Methods:
    1. 'hip_only' - Original method (hip midpoint)
    2. 'center_mass' - Estimated center of mass
    3. 'multi_point' - Average of multiple body points
    4. 'foot_clearance' - Based on foot lift-off
    """
    
    hip_y = np.array(hip_y_values)
    knee_y = np.array(knee_y_values) 
    ankle_y = np.array(ankle_y_values)
    
    if method == "hip_only":
        return calculate_hip_method(hip_y)
    elif method == "center_mass":
        return calculate_center_mass_method(hip_y, knee_y, ankle_y)
    elif method == "multi_point":
        return calculate_multi_point_method(hip_y, knee_y, ankle_y)
    elif method == "foot_clearance":
        return calculate_foot_clearance_method(ankle_y, fps)

def calculate_hip_method(hip_y):
    """Original method - hip midpoint tracking"""
    # Smooth the data
    smoothed = savgol_filter(hip_y, window_length=min(11, len(hip_y)//2*2+1), polyorder=2)
    
    # Dynamic baseline detection
    baseline = find_stable_baseline(smoothed)
    peak_y = np.min(smoothed)
    
    jump_height = baseline - peak_y
    
    return {
        'method': 'Hip Tracking',
        'jump_height_px': jump_height,
        'baseline_y': baseline,
        'peak_y': peak_y,
        'confidence': calculate_confidence(hip_y),
        'smoothed_data': smoothed
    }

def calculate_center_mass_method(hip_y, knee_y, ankle_y):
    """Estimate center of mass using body segment weights"""
    
    # Anthropometric data (% of body weight)
    # Using simplified model: 60% hip + 25% knee + 15% ankle
    center_mass_y = 0.60 * hip_y + 0.25 * knee_y + 0.15 * ankle_y
    
    smoothed = savgol_filter(center_mass_y, window_length=min(11, len(center_mass_y)//2*2+1), polyorder=2)
    
    baseline = find_stable_baseline(smoothed)
    peak_y = np.min(smoothed)
    jump_height = baseline - peak_y
    
    return {
        'method': 'Center of Mass',
        'jump_height_px': jump_height,
        'baseline_y': baseline,
        'peak_y': peak_y,
        'confidence': calculate_confidence(center_mass_y),
        'smoothed_data': smoothed
    }

def calculate_multi_point_method(hip_y, knee_y, ankle_y):
    """Average multiple body points for stability"""
    
    # Calculate jump height for each body part
    hip_jump = find_stable_baseline(hip_y) - np.min(hip_y)
    knee_jump = find_stable_baseline(knee_y) - np.min(knee_y) 
    ankle_jump = find_stable_baseline(ankle_y) - np.min(ankle_y)
    
    # Weighted average (hip is most stable)
    jump_height = 0.5 * hip_jump + 0.3 * knee_jump + 0.2 * ankle_jump
    
    # For visualization, use hip data as primary
    hip_smoothed = savgol_filter(hip_y, window_length=min(11, len(hip_y)//2*2+1), polyorder=2)
    baseline = find_stable_baseline(hip_y)
    peak_y = baseline - jump_height
    
    return {
        'method': 'Multi-Point Average',
        'jump_height_px': jump_height,
        'hip_jump': hip_jump,
        'knee_jump': knee_jump,
        'ankle_jump': ankle_jump,
        'baseline_y': baseline,
        'peak_y': peak_y,
        'confidence': (calculate_confidence(hip_y) + calculate_confidence(knee_y)) / 2,
        'smoothed_data': hip_smoothed
    }

def calculate_foot_clearance_method(ankle_y, fps):
    """Calculate based on foot lift-off time and physics"""
    
    smoothed = savgol_filter(ankle_y, window_length=min(11, len(ankle_y)//2*2+1), polyorder=2)
    
    # Find takeoff and landing points
    baseline = find_stable_baseline(smoothed)
    
    # Find when feet leave ground (10% threshold)
    threshold = baseline - (baseline - np.min(smoothed)) * 0.1
    
    takeoff_idx = None
    landing_idx = None
    
    for i in range(len(smoothed)):
        if smoothed[i] < threshold and takeoff_idx is None:
            takeoff_idx = i
        elif takeoff_idx is not None and smoothed[i] > threshold:
            landing_idx = i
            break
    
    direct_height = baseline - np.min(smoothed)
    
    result = {
        'method': 'Foot Clearance + Physics',
        'jump_height_px': direct_height,
        'baseline_y': baseline,
        'peak_y': np.min(smoothed),
        'confidence': calculate_confidence(ankle_y),
        'smoothed_data': smoothed
    }
    
    if takeoff_idx is not None and landing_idx is not None:
        # Flight time method using physics
        flight_time = (landing_idx - takeoff_idx) / fps
        
        # Using physics: h = (g * t²) / 8
        physics_height_m = (9.81 * flight_time**2) / 8
        physics_height_cm = physics_height_m * 100
        
        result.update({
            'physics_height_cm': physics_height_cm,
            'flight_time': flight_time,
            'takeoff_frame': takeoff_idx,
            'landing_frame': landing_idx
        })
    
    return result

def find_stable_baseline(y_values, stability_window=10):
    """Find stable baseline by looking for the most common Y position"""
    
    # Method 1: Histogram approach
    hist, bin_edges = np.histogram(y_values, bins=50)
    most_common_bin = np.argmax(hist)
    baseline_hist = (bin_edges[most_common_bin] + bin_edges[most_common_bin + 1]) / 2
    
    # Method 2: Stable periods approach
    stable_values = []
    for i in range(len(y_values) - stability_window):
        window = y_values[i:i+stability_window]
        if np.std(window) < np.std(y_values) * 0.1:  # Low variation = stable
            stable_values.extend(window)
    
    if len(stable_values) > 0:
        baseline_stable = np.median(stable_values)
    else:
        baseline_stable = np.percentile(y_values, 75)  # Fallback
    
    # Use the higher baseline (more conservative)
    return max(baseline_hist, baseline_stable)

def calculate_confidence(y_values):
    """Calculate confidence score based on data quality"""
    
    if len(y_values) < 10:
        return 0.1
    
    smoothed = savgol_filter(y_values, window_length=min(11, len(y_values)//2*2+1), polyorder=2)
    
    # Noise level (lower is better)
    noise_level = np.mean(np.abs(y_values - smoothed))
    noise_score = max(0, 1 - noise_level / (np.std(y_values) + 1e-6))
    
    # Jump clarity (clear peak vs flat)
    range_val = np.max(y_values) - np.min(y_values)
    range_score = min(1, range_val / (np.std(y_values) * 3 + 1e-6))
    
    # Data length
    length_score = min(1, len(y_values) / 30)  # Prefer 30+ frames
    
    confidence = (noise_score * 0.4 + range_score * 0.4 + length_score * 0.2)
    return round(max(0, min(1, confidence)), 2)

# =========================
# 📌 Calibration Functions
# =========================
def get_pixels_per_cm_from_height(video_path, person_height_cm=170):
    """Calibrate using person's known height"""
    cap = cv2.VideoCapture(video_path)
    
    head_to_foot_distances = []
    
    for _ in range(30):  # Sample first 30 frames
        ret, frame = cap.read()
        if not ret:
            break
            
        results = model(frame, verbose=False)
        
        if results[0].keypoints is not None:
            kps = results[0].keypoints.xy.cpu().numpy()[0]
            
            # Get head (nose) and feet keypoints
            nose = kps[0]  # nose keypoint
            left_ankle = kps[15]
            right_ankle = kps[16]
            
            # Calculate foot position (midpoint of ankles)
            if nose[1] > 0 and left_ankle[1] > 0 and right_ankle[1] > 0:
                foot_y = (left_ankle[1] + right_ankle[1]) / 2
                head_to_foot_px = abs(foot_y - nose[1])
                head_to_foot_distances.append(head_to_foot_px)
    
    cap.release()
    
    if head_to_foot_distances:
        avg_body_height_px = np.median(head_to_foot_distances)
        pixels_per_cm = avg_body_height_px / person_height_cm
        return pixels_per_cm
    
    return None

def get_pixels_per_cm_manual_calibration():
    """Manual calibration method"""
    print("=== MANUAL CALIBRATION ===")
    print("Options:")
    print("1. Place a reference object (ruler, water bottle, etc.) in the scene")
    print("2. Use person's height")
    print("3. Use standard measurements (door frame, etc.)")
    
    method = input("Choose calibration method (1/2/3): ")
    
    if method == "1":
        ref_length_cm = float(input("Enter reference object length in CM: "))
        ref_length_px = float(input("Enter reference object length in PIXELS (measure from video): "))
        return ref_length_px / ref_length_cm
    
    elif method == "2":
        person_height_cm = float(input("Enter person's height in CM: "))
        video_path = input("Enter video path for auto-detection: ")
        return get_pixels_per_cm_from_height(video_path, person_height_cm)
    
    elif method == "3":
        print("Standard reference heights:")
        print("- Door frame: ~200-210 cm")
        print("- Basketball hoop: 305 cm")
        print("- Standard ceiling: ~240-270 cm")
        ref_height_cm = float(input("Enter reference height in CM: "))
        ref_height_px = float(input("Enter reference height in PIXELS: "))
        return ref_height_px / ref_height_cm

# =========================
# 📌 Enhanced Vertical Jump Analysis with All Methods
# =========================
def analyze_vertical_jump_complete(video_path, output_path="output_jump.mp4", 
                                 calibration_method="auto", person_height_cm=170,
                                 calculation_method="all"):
    """
    Complete vertical jump analysis with improved calculations
    
    calibration_method: 'auto', 'manual', or 'height'
    calculation_method: 'hip_only', 'center_mass', 'multi_point', 'foot_clearance', or 'all'
    """
    
    # =========================
    # 📌 Calibration
    # =========================
    pixels_per_cm = None
    
    if calibration_method == "auto":
        pixels_per_cm = get_pixels_per_cm_from_height(video_path, person_height_cm)
        if pixels_per_cm is None:
            print("Auto-calibration failed. Switching to manual calibration.")
            pixels_per_cm = get_pixels_per_cm_manual_calibration()
    
    elif calibration_method == "manual":
        pixels_per_cm = get_pixels_per_cm_manual_calibration()
    
    elif calibration_method == "height":
        pixels_per_cm = get_pixels_per_cm_from_height(video_path, person_height_cm)
    
    if pixels_per_cm is None:
        print("Calibration failed. Using pixel measurements only.")
    else:
        print(f"Calibration: {pixels_per_cm:.2f} pixels per cm")
    
    # =========================
    # 📌 Video Analysis
    # =========================
    cap = cv2.VideoCapture(video_path)
    
    # Save annotated output video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Data collection arrays
    hip_y_values = []
    knee_y_values = []
    ankle_y_values = []
    frame_idx = 0

    print(f"Processing video... FPS: {fps}")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, verbose=False)

        # Get keypoints
        if results[0].keypoints is not None:
            kps = results[0].keypoints.xy.cpu().numpy()[0]  # first person
            
            # Hip midpoint (left hip = 11, right hip = 12 in COCO)
            left_hip = kps[11]
            right_hip = kps[12]
            if left_hip[0] > 0 and right_hip[0] > 0:  # Valid keypoints
                mid_hip_y = (left_hip[1] + right_hip[1]) / 2
                hip_y_values.append(mid_hip_y)
            else:
                hip_y_values.append(hip_y_values[-1] if hip_y_values else 0)
            
            # Knee midpoint (left knee = 13, right knee = 14)
            left_knee = kps[13]
            right_knee = kps[14]
            if left_knee[0] > 0 and right_knee[0] > 0:
                mid_knee_y = (left_knee[1] + right_knee[1]) / 2
                knee_y_values.append(mid_knee_y)
            else:
                knee_y_values.append(knee_y_values[-1] if knee_y_values else 0)
            
            # Ankle midpoint (left ankle = 15, right ankle = 16)
            left_ankle = kps[15]
            right_ankle = kps[16]
            if left_ankle[0] > 0 and right_ankle[0] > 0:
                mid_ankle_y = (left_ankle[1] + right_ankle[1]) / 2
                ankle_y_values.append(mid_ankle_y)
            else:
                ankle_y_values.append(ankle_y_values[-1] if ankle_y_values else 0)

            # Draw keypoints on frame
            hip_center = (int((left_hip[0] + right_hip[0]) / 2), int((left_hip[1] + right_hip[1]) / 2))
            knee_center = (int((left_knee[0] + right_knee[0]) / 2), int((left_knee[1] + right_knee[1]) / 2))
            ankle_center = (int((left_ankle[0] + right_ankle[0]) / 2), int((left_ankle[1] + right_ankle[1]) / 2))
            
            # Draw circles and labels
            cv2.circle(frame, hip_center, 8, (0,255,0), -1)  # Green hip
            cv2.circle(frame, knee_center, 6, (255,0,0), -1)  # Blue knee
            cv2.circle(frame, ankle_center, 6, (0,0,255), -1)  # Red ankle
            
            cv2.putText(frame, "Hip", (hip_center[0]+10, hip_center[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
            cv2.putText(frame, "Knee", (knee_center[0]+10, knee_center[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)
            cv2.putText(frame, "Ankle", (ankle_center[0]+10, ankle_center[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)

        # Add frame info
        cv2.putText(frame, f"Frame: {frame_idx}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

        # Save annotated frame
        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()

    # =========================
    # 📌 Jump Analysis with Multiple Methods
    # =========================
    if len(hip_y_values) == 0:
        print("No person detected in the video.")
        return

    print(f"Analyzing {len(hip_y_values)} frames...")

    # Calculate using all methods
    methods_to_test = ['hip_only', 'center_mass', 'multi_point', 'foot_clearance'] if calculation_method == "all" else [calculation_method]
    
    results_all = {}
    
    print("\n🏀 JUMP HEIGHT CALCULATION RESULTS")
    print("=" * 60)
    
    for method in methods_to_test:
        try:
            result = calculate_jump_height_improved(hip_y_values, knee_y_values, ankle_y_values, fps, method)
            results_all[method] = result
            
            height_px = result['jump_height_px']
            height_cm = height_px / pixels_per_cm if pixels_per_cm else None
            confidence = result.get('confidence', 0)
            
            print(f"\n📊 {result['method']}:")
            print(f"   Height: {height_px:.1f} px", end="")
            if height_cm:
                print(f" ({height_cm:.1f} cm)")
            else:
                print()
            print(f"   Confidence: {confidence:.2f}")
            
            if 'physics_height_cm' in result:
                print(f"   Physics-based: {result['physics_height_cm']:.1f} cm")
                print(f"   Flight time: {result['flight_time']:.2f} s")
                
                if pixels_per_cm and height_cm:
                    diff = abs(result['physics_height_cm'] - height_cm)
                    print(f"   Difference: {diff:.1f} cm ({diff/height_cm*100:.1f}%)")
        
        except Exception as e:
            print(f"❌ {method} failed: {e}")
    
    # Find best method
    if results_all:
        best_method_key = max(results_all.keys(), key=lambda k: results_all[k].get('confidence', 0))
        best_result = results_all[best_method_key]
        print(f"\n🏆 RECOMMENDED METHOD: {best_result['method']}")
        
        best_height_px = best_result['jump_height_px']
        best_height_cm = best_height_px / pixels_per_cm if pixels_per_cm else None
        
        if best_height_cm:
            print(f"🎯 FINAL RESULT: {best_height_cm:.1f} cm")
        else:
            print(f"🎯 FINAL RESULT: {best_height_px:.1f} pixels")

    # =========================
    # 📌 Enhanced Visualization
    # =========================
    plt.figure(figsize=(16, 12))
    
    # Create time axis
    time_axis = np.arange(len(hip_y_values)) / fps
    
    # Plot 1: Raw data comparison
    plt.subplot(3, 2, 1)
    plt.plot(time_axis, hip_y_values, label="Hip Y", alpha=0.7, color='green')
    plt.plot(time_axis, knee_y_values, label="Knee Y", alpha=0.7, color='blue')
    plt.plot(time_axis, ankle_y_values, label="Ankle Y", alpha=0.7, color='red')
    plt.legend()
    plt.title("Raw Joint Movement Data")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Y position (pixels)")
    plt.gca().invert_yaxis()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: Best method detailed view
    plt.subplot(3, 2, 2)
    if results_all:
        best_data = best_result['smoothed_data']
        plt.plot(time_axis, best_data, label=f"Smoothed ({best_result['method']})", linewidth=2)
        plt.axhline(best_result['baseline_y'], color='g', linestyle='--', label="Baseline")
        plt.axhline(best_result['peak_y'], color='r', linestyle='--', label="Peak")
        
        # Add takeoff/landing if available
        if 'takeoff_frame' in best_result:
            plt.axvline(best_result['takeoff_frame']/fps, color='orange', linestyle=':', label="Takeoff")
            plt.axvline(best_result['landing_frame']/fps, color='purple', linestyle=':', label="Landing")
        
        plt.legend()
        title_text = f"{best_result['method']} - "
        if best_height_cm:
            title_text += f"{best_height_cm:.1f} cm"
        else:
            title_text += f"{best_height_px:.1f} px"
        plt.title(title_text)
        plt.xlabel("Time (seconds)")
        plt.ylabel("Y position (pixels)")
        plt.gca().invert_yaxis()
        plt.grid(True, alpha=0.3)
    
    # Plot 3: Method comparison
    plt.subplot(3, 2, 3)
    if len(results_all) > 1:
        methods = list(results_all.keys())
        heights = [results_all[m]['jump_height_px'] / pixels_per_cm if pixels_per_cm else results_all[m]['jump_height_px'] for m in methods]
        confidences = [results_all[m]['confidence'] for m in methods]
        
        bars = plt.bar(methods, heights, color=['green', 'blue', 'orange', 'red'][:len(methods)], alpha=0.7)
        
        # Add confidence as text on bars
        for bar, conf in zip(bars, confidences):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(heights)*0.01,
                    f'Conf: {conf:.2f}', ha='center', va='bottom', fontsize=8)
        
        plt.title("Method Comparison")
        plt.ylabel("Jump Height (cm)" if pixels_per_cm else "Jump Height (px)")
        plt.xticks(rotation=45, ha='right')
    
    # Plot 4: Physics validation (if available)
    plt.subplot(3, 2, 4)
    physics_methods = {k: v for k, v in results_all.items() if 'physics_height_cm' in v}
    if physics_methods and pixels_per_cm:
        for method_name, result in physics_methods.items():
            pixel_height_cm = result['jump_height_px'] / pixels_per_cm
            physics_height_cm = result['physics_height_cm']
            
            plt.scatter(pixel_height_cm, physics_height_cm, s=100, label=method_name, alpha=0.7)
        
        # Perfect correlation line
        max_val = max([r['physics_height_cm'] for r in physics_methods.values()])
        plt.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label='Perfect match')
        
        plt.xlabel("Pixel-based Height (cm)")
        plt.ylabel("Physics-based Height (cm)")
        plt.title("Physics Validation")
        plt.legend()
        plt.grid(True, alpha=0.3)
    
    # Plot 5: Confidence scores
    plt.subplot(3, 2, 5)
    if results_all:
        methods = list(results_all.keys())
        confidences = [results_all[m]['confidence'] for m in methods]
        colors = ['green', 'blue', 'orange', 'red'][:len(methods)]
        
        bars = plt.bar(methods, confidences, color=colors, alpha=0.7)
        plt.ylim(0, 1)
        plt.title("Method Confidence Scores")
        plt.ylabel("Confidence")
        plt.xticks(rotation=45, ha='right')
        
        # Add threshold line
        plt.axhline(0.7, color='red', linestyle='--', alpha=0.5, label='Good threshold')
        plt.legend()
    
    # Plot 6: Flight analysis (if available)
    plt.subplot(3, 2, 6)
    flight_methods = {k: v for k, v in results_all.items() if 'flight_time' in v}
    if flight_methods:
        for method_name, result in flight_methods.items():
            flight_time = result['flight_time']
            takeoff = result['takeoff_frame']
            landing = result['landing_frame']
            
            # Plot ankle data with flight phase highlighted
            plt.plot(time_axis, ankle_y_values, alpha=0.5, color='red', label='Ankle position')
            plt.axvspan(takeoff/fps, landing/fps, alpha=0.3, color='yellow', label='Flight phase')
            plt.axvline(takeoff/fps, color='orange', linestyle='--', label='Takeoff')
            plt.axvline(landing/fps, color='purple', linestyle='--', label='Landing')
            
        plt.title(f"Flight Analysis - {flight_time:.2f}s")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Ankle Y position (pixels)")
        plt.gca().invert_yaxis()
        plt.legend()
        plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

    print(f"\n📹 Annotated video saved at: {output_path}")
    
    return results_all

# =========================
# 📌 Main Usage Function
# =========================
def run_complete_vertical_jump_analysis():
    """Main function to run the complete analysis"""
    print("🏀 COMPLETE VERTICAL JUMP ANALYZER")
    print("=" * 50)
    
    video_path = input("Enter video path: ")
    
    print("\nCalibration options:")
    print("1. Auto (using person's height estimation)")
    print("2. Manual (with reference object)")
    print("3. Height (specify person's height)")
    
    cal_choice = input("Choose calibration method (1/2/3): ")
    
    print("\nCalculation method options:")
    print("1. Hip only (original)")
    print("2. Center of mass")
    print("3. Multi-point average")
    print("4. Foot clearance + physics")
    print("5. All methods (recommended)")
    
    calc_choice = input("Choose calculation method (1/2/3/4/5): ")
    
    # Map choices
    cal_methods = {'1': 'auto', '2': 'manual', '3': 'height'}
    calc_methods_map = {
        '1': 'hip_only', 
        '2': 'center_mass', 
        '3': 'multi_point', 
        '4': 'foot_clearance', 
        '5': 'all'
    }
    
    calibration_method = cal_methods.get(cal_choice, 'auto')
    calculation_method = calc_methods_map.get(calc_choice, 'all')
    
    person_height = 170
    if calibration_method in ['auto', 'height']:
        height_input = input("Enter person's height in cm (default 170): ")
        if height_input.strip():
            person_height = float(height_input)
    
    results = analyze_vertical_jump_complete(
        video_path, 
        calibration_method=calibration_method,
        calculation_method=calculation_method,
        person_height_cm=person_height
    )
    
    return results

# =========================
# 📌 Run Analysis
# =========================
# Uncomment to run:
run_complete_vertical_jump_analysis()