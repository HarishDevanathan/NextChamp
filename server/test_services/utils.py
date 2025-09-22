# utils.py
import cv2
import numpy as np
import os
import mediapipe as mp
from enum import Enum
from collections import Counter
import time
import json
import requests
from datetime import datetime
import uuid
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Try to import reportlab, provide a fallback if not installed
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER

    _reportlab_available = True
except ImportError:
    _reportlab_available = False
    print("Warning: reportlab not installed. PDF export will not be available. Please run 'pip install reportlab'")

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# MongoDB connection will be initialized from environment variables
mongo_client = None
db = None
results_collection = None

async def init_database():
    """Initialize MongoDB connection"""
    global mongo_client, db, results_collection
    
    mongo_uri = os.getenv('MONGO_URI')
    mongo_db_name = os.getenv('MONGO_DB_NAME', 'NextChamp')
    
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    
    mongo_client = AsyncIOMotorClient(mongo_uri)
    db = mongo_client[mongo_db_name]
    results_collection = db['result']
    
    print(f"✅ Connected to MongoDB: {mongo_db_name}")

class ExerciseType(Enum):
    VERTICAL_JUMP = 0
    SHUTTLE_RUN = 1
    SITUPS = 2
    PUSHUPS = 3
    PLANK_HOLD = 4
    STANDING_BROAD_JUMP = 5
    SQUATS = 6
    ENDURANCE_RUN = 7

class UserProfile:
    def __init__(self, name="", age=0, height=0, weight=0, user_id=None):
        self.name = name
        self.age = age
        self.height = height
        self.weight = weight
        self.user_id = user_id or str(ObjectId())

    def get_bmi(self):
        if self.height > 0 and self.weight > 0:
            height_m = self.height / 100
            return self.weight / (height_m ** 2)
        return 0

    def get_fitness_level(self):
        bmi = self.get_bmi()
        if bmi < 18.5:
            return "Underweight"
        elif bmi < 25:
            return "Normal weight"
        elif bmi < 30:
            return "Overweight"
        else:
            return "Obese"

class ExerciseAnalyzer:
    def __init__(self, user_profile=None):
        self.pose = mp_pose.Pose(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.user_profile = user_profile or UserProfile()
        self.exercise_type = None
        self.rep_count = 0
        self.is_correct_form = True
        self.feedback = ""
        self.previous_state = "up"  # Track squat/pushup state: "up", "down", "transition"
        self.rep_phase = "waiting"  # "going_down", "at_bottom", "going_up", "at_top"
        self.frame_counter = 0
        self.state_confidence = 0
        self.reference_metrics = {}
        self.feedback_history = []
        self.metrics_history = []
        self.start_time = None
        self.form_errors = {
            'knee_alignment': 0,
            'depth_issues': 0,
            'torso_lean': 0,
            'elbow_position': 0,
            'body_alignment': 0,
            'landing_form': 0,
            'takeoff_form': 0,
            'jump_asymmetry': 0
        }
        self.rep_quality_scores = []  # Store quality score for each rep
        
        # Standing broad jump specific attributes
        self.jump_distances = []  # Store all jump distances
        self.best_distance = 0
        self.current_jump_distance = 0
        self.jump_attempts = 0
        self.baseline_established = False
        self.jump_start_position = None
        self.jump_landing_position = None
        self.calibration_frames = 0
        self.calibration_positions = []

        self.shuttle_runs = []  # Store completed shuttle runs
        self.current_shuttle_distance = 0
        self.shuttle_attempts = 0
        self.direction_changes = 0
        self.shuttle_start_time = None
        self.shuttle_positions = []  # Track position history
        self.current_direction = None  # 'left', 'right', or 'stationary'
        self.last_direction_change_pos = None
        self.turn_start_time = None
        self.running_start_pos = None
        self.max_left_position = None
        self.max_right_position = None
        self.shuttle_run_times = []  # Store time for each shuttle run
        self.last_run_start_time = None
        self.total_shuttle_time = 0
        self.average_shuttle_time = 0
        self.all_feedback_per_frame = []  # Store feedback for each frame
        self.detailed_metrics_per_frame = []

    def detect_squat_phase(self, knee_angle, hip_height):
        """Detect what phase of squat movement user is in"""
        current_phase = self.rep_phase
        
        # Define thresholds for squat phases
        TOP_KNEE_ANGLE = 160  # Nearly straight legs
        BOTTOM_KNEE_ANGLE = 100  # Deep squat position
        
        if knee_angle > TOP_KNEE_ANGLE:
            if current_phase == "going_up":
                # Just completed a rep!
                self.rep_count += 1
                # Calculate rep quality score
                rep_quality = self.calculate_rep_quality()
                self.rep_quality_scores.append(rep_quality)
                return "at_top"
            return "at_top"
        elif knee_angle < BOTTOM_KNEE_ANGLE:
            return "at_bottom"
        elif current_phase in ["at_top", "going_up"] and knee_angle < 150:
            return "going_down"
        elif current_phase in ["at_bottom", "going_down"] and knee_angle > 110:
            return "going_up"
        else:
            return current_phase
    
    def detect_jump_phase(self, hip_height, knee_angle, ankle_height):
        """Detect what phase of vertical jump movement user is in"""
        current_phase = self.rep_phase
        
        # Define thresholds for jump phases based on relative positions
        BASELINE_HIP_HEIGHT = getattr(self, 'baseline_hip_height', None)
        PREP_KNEE_ANGLE = 120  # Bent knees in preparation
        TAKEOFF_THRESHOLD = 0.85  # Relative height for takeoff detection
        LANDING_THRESHOLD = 0.95  # Close to baseline for landing
        
        # Initialize baseline on first frames
        if BASELINE_HIP_HEIGHT is None:
            self.baseline_hip_height = hip_height
            self.baseline_ankle_height = ankle_height
            return "at_baseline"
        
        # Calculate relative height (lower values = higher jump)
        relative_height = hip_height / self.baseline_hip_height
        
        if current_phase == "at_baseline" and knee_angle < PREP_KNEE_ANGLE:
            return "preparing"
        elif current_phase == "preparing" and relative_height < TAKEOFF_THRESHOLD:
            return "takeoff"
        elif current_phase == "takeoff" and relative_height < 0.7:  # Peak of jump
            return "in_air"
        elif current_phase == "in_air" and relative_height > LANDING_THRESHOLD:
            # Just completed a jump!
            self.rep_count += 1
            rep_quality = self.calculate_rep_quality()
            self.rep_quality_scores.append(rep_quality)
            return "landing"
        elif current_phase == "landing" and knee_angle > 150:  # Standing back up
            return "at_baseline"
        else:
            return current_phase
    
    def detect_pushup_phase(self, elbow_angle, shoulder_height):
        """Detect what phase of pushup movement user is in"""
        current_phase = self.rep_phase
        
        # Define thresholds for pushup phases
        TOP_ELBOW_ANGLE = 160  # Nearly straight arms
        BOTTOM_ELBOW_ANGLE = 90  # Deep pushup position
        
        if elbow_angle > TOP_ELBOW_ANGLE:
            if current_phase == "going_up":
                # Just completed a rep!
                self.rep_count += 1
                rep_quality = self.calculate_rep_quality()
                self.rep_quality_scores.append(rep_quality)
                return "at_top"
            return "at_top"
        elif elbow_angle < BOTTOM_ELBOW_ANGLE:
            return "at_bottom"
        elif current_phase in ["at_top", "going_up"] and elbow_angle < 150:
            return "going_down"
        elif current_phase in ["at_bottom", "going_down"] and elbow_angle > 100:
            return "going_up"
        else:
            return current_phase
    
    def detect_situp_phase(self, torso_angle, shoulder_height, hip_height):
        """Detect what phase of sit-up movement user is in"""
        current_phase = self.rep_phase
        
        # Define thresholds for sit-up phases
        DOWN_TORSO_ANGLE = 15   # Nearly lying flat (small angle between torso and ground)
        UP_TORSO_ANGLE = 60   # Sitting up position (larger angle)
        #TRANSITION_THRESHOLD = 10  # Threshold for detecting transitions
        
        # Calculate relative shoulder position (higher value = more upright)
        #shoulder_hip_diff = hip_height - shoulder_height
        
        if torso_angle <= DOWN_TORSO_ANGLE:
            if current_phase == "going_down":
                # Just completed a rep by going back down!
                self.rep_count += 1
                rep_quality = self.calculate_rep_quality()
                self.rep_quality_scores.append(rep_quality)
                return "at_bottom"
            return "at_bottom"
        elif torso_angle >= UP_TORSO_ANGLE:
            return "at_top"
        elif current_phase in ["at_bottom", "going_up"] and torso_angle > (DOWN_TORSO_ANGLE + 5):
            return "going_up"
        elif current_phase in ["at_top", "going_down"] and torso_angle < (UP_TORSO_ANGLE - 5):
            return "going_down"
        else:
            return current_phase
        
    def detect_broad_jump_phase(self, hip_x_position, knee_angle, ankle_height, frame_width):
        """Detect what phase of standing broad jump movement user is in with distance tracking"""
        current_phase = self.rep_phase
        
        # Calibration phase - establish baseline position
        if not self.baseline_established:
            self.calibration_positions.append(hip_x_position)
            self.calibration_frames += 1
            
            if self.calibration_frames >= 30:  # Calibrate over 30 frames (1 second at 30fps)
                self.baseline_hip_x = np.mean(self.calibration_positions)
                self.baseline_established = True
                return "at_baseline"
            else:
                return "calibrating"
        
        # Define thresholds for broad jump phases
        PREP_KNEE_ANGLE = 120  # Bent knees in preparation
        TAKEOFF_MOVEMENT_THRESHOLD = 0.02 * frame_width  # 2% of frame width
        SIGNIFICANT_MOVEMENT_THRESHOLD = 0.05 * frame_width  # 5% of frame width
        LANDING_STABILITY_FRAMES = 15  # Frames to wait for landing stability
        
        # Calculate horizontal displacement from baseline
        horizontal_displacement = hip_x_position - self.baseline_hip_x
        abs_displacement = abs(horizontal_displacement)

        # Add this line here:
        max_trajectory_displacement = self.track_jump_trajectory(hip_x_position)
        
        # State machine for broad jump detection
        if current_phase == "at_baseline" and knee_angle < PREP_KNEE_ANGLE:
            self.jump_start_position = hip_x_position
            return "preparing"
            
        elif current_phase == "preparing" and abs_displacement > TAKEOFF_MOVEMENT_THRESHOLD:
            return "takeoff"
            
        elif current_phase == "takeoff" and abs_displacement > SIGNIFICANT_MOVEMENT_THRESHOLD:
            return "in_air"
            
        elif current_phase == "in_air":
            # Track maximum displacement during flight
            if not hasattr(self, 'max_displacement_this_jump'):
                self.max_displacement_this_jump = abs_displacement
            else:
                self.max_displacement_this_jump = max(self.max_displacement_this_jump, abs_displacement)
            
            # Check for landing (reduced movement and bent knees)
            if knee_angle < 150 and abs_displacement > SIGNIFICANT_MOVEMENT_THRESHOLD:
                self.jump_landing_position = hip_x_position
                self.landing_stability_counter = 0
                return "landing"
                
        elif current_phase == "landing":
            self.landing_stability_counter += 1

            # Track the furthest position during landing phase
            if not hasattr(self, 'furthest_position_this_jump'):
                self.furthest_position_this_jump = hip_x_position
            else:
        # Update furthest position if we've moved further
                if abs(hip_x_position - self.baseline_hip_x) > abs(self.furthest_position_this_jump - self.baseline_hip_x):
                  self.furthest_position_this_jump = hip_x_position
            
            # Once stable, calculate and record the jump distance
            if self.landing_stability_counter >= LANDING_STABILITY_FRAMES:
                # #Calculate jump distance

                # if self.jump_start_position is not None and self.jump_landing_position is not None:
                #     jump_distance_pixels = abs(self.jump_landing_position - self.jump_start_position)
                #     # Convert to relative distance (percentage of frame width)
                #     jump_distance_relative = (jump_distance_pixels / frame_width) * 100
                    
                #     # Store the jump distance

                #     self.current_jump_distance = jump_distance_relative
                #     self.jump_distances.append(jump_distance_relative)
                #     self.best_distance = max(self.best_distance, jump_distance_relative)
                #     self.jump_attempts += 1
                    
                #     # Reset for next jump

                #     self.max_displacement_this_jump = 0
                #     self.jump_start_position = None
                #     self.jump_landing_position = None

                trajectory_distance = self.track_jump_trajectory(hip_x_position)
                if trajectory_distance > 0:
        # Convert to relative distance (percentage of frame width)
                  jump_distance_relative = (trajectory_distance / frame_width) * 100
                else:
        # Fallback to furthest position method
                   if hasattr(self, 'furthest_position_this_jump'):
                      jump_distance_pixels = abs(self.furthest_position_this_jump - self.baseline_hip_x)
                      jump_distance_relative = (jump_distance_pixels / frame_width) * 100
                   else:
                      jump_distance_relative = 0
    
    # Store the jump distance
                self.current_jump_distance = jump_distance_relative
                self.jump_distances.append(jump_distance_relative)
                self.best_distance = max(self.best_distance, jump_distance_relative)
                self.jump_attempts += 1
    
    # Reset for next jump
                if hasattr(self, 'furthest_position_this_jump'):
                  delattr(self, 'furthest_position_this_jump')
                self.jump_start_position = None
                self.jump_landing_position = None
                    
                return "completed"
                
        elif current_phase == "completed" and knee_angle > 150:  # Standing back up
            return "at_baseline"
            
        return current_phase
    
    def detect_plank_phase(self, shoulder_hip_ankle_angle, elbow_angle, hold_time):
        """Detect plank hold phase and track duration"""
        current_phase = self.rep_phase
    
    # Define thresholds for plank hold
        GOOD_PLANK_ANGLE_MIN = 150  # Nearly straight body line
        GOOD_PLANK_ANGLE_MAX = 200  # Allow some variation
        STABLE_ELBOW_ANGLE = 90     # 90-degree elbow angle
        MIN_HOLD_TIME = 5          # Minimum 10 seconds for a valid hold
    
        if (GOOD_PLANK_ANGLE_MIN <= shoulder_hip_ankle_angle <= GOOD_PLANK_ANGLE_MAX and 
              60 <= elbow_angle <= 130):
           if current_phase != "holding":
             self.plank_start_time = time.time()
             return "holding"
           return "holding"
        else:
          return "not_holding"
        
    def detect_shuttle_run_phase(self, hip_x_position, knee_angle, movement_speed, frame_width):
      """Detect shuttle run phase with direction changes and distance tracking"""
      current_phase = self.rep_phase
    
    # Initialize baseline on first run
      if not hasattr(self, 'shuttle_baseline_x'):
        self.shuttle_baseline_x = hip_x_position
        self.max_left_position = hip_x_position
        self.max_right_position = hip_x_position
        self.current_direction = None
        return "at_start"
    
    # Track position extremes
      self.max_left_position = min(self.max_left_position, hip_x_position)
      self.max_right_position = max(self.max_right_position, hip_x_position)
    
    # Calculate thresholds
      DIRECTION_CHANGE_THRESHOLD = self.reference_metrics['direction_change_threshold'] * frame_width
      SPEED_THRESHOLD = self.reference_metrics['speed_threshold'] * frame_width
      STATIONARY_THRESHOLD = self.reference_metrics['stationary_threshold'] * frame_width
    
    # Determine current movement direction based on movement speed and direction
      new_direction = None
      if movement_speed > SPEED_THRESHOLD:
        if len(self.shuttle_positions) >= 2:
            position_change = hip_x_position - self.shuttle_positions[-2]  # Compare to 2 frames ago for stability
            if abs(position_change) > SPEED_THRESHOLD:  # Only if significant movement
                if position_change > 0:
                    new_direction = 'right'
                else:
                    new_direction = 'left'
        else:
            new_direction = 'right'  # Default start direction
      else:
        new_direction = 'stationary'
    
    # CRITICAL: Detect direction changes BEFORE updating state machine
      direction_changed = False
      if (self.current_direction and 
        self.current_direction != new_direction and 
        new_direction != 'stationary' and 
        self.current_direction != 'stationary'):
        
        # Significant direction change detected
        if (self.last_direction_change_pos is None or 
            abs(hip_x_position - self.last_direction_change_pos) > DIRECTION_CHANGE_THRESHOLD):
            
            self.direction_changes += 1
            self.last_direction_change_pos = hip_x_position
            self.turn_start_time = time.time()
            
            # Record shuttle run time if we have a previous run
            if hasattr(self, 'last_run_start_time') and self.last_run_start_time:
                run_time = time.time() - self.last_run_start_time
                if not hasattr(self, 'shuttle_run_times'):
                    self.shuttle_run_times = []
                self.shuttle_run_times.append(run_time)
            
            direction_changed = True
    
    # Update current direction
      if new_direction != 'stationary':
        self.current_direction = new_direction
    
    # State machine for shuttle run phases
      if current_phase == "at_start":
        if movement_speed > SPEED_THRESHOLD:
            self.shuttle_start_time = time.time()
            self.last_run_start_time = time.time()
            self.running_start_pos = hip_x_position
            return "running"
        return "at_start"
    
      elif current_phase == "running":
        if direction_changed:
            return "turning"
        elif movement_speed < STATIONARY_THRESHOLD:
            return "turning"
        return "running"
    
      elif current_phase == "turning":
        if hasattr(self, 'turn_start_time') and self.turn_start_time:
            turn_duration = time.time() - self.turn_start_time
            if movement_speed > SPEED_THRESHOLD and turn_duration > 0.5:  # Turn complete, back to running
                self.last_run_start_time = time.time()  # Start timing next run
                return "running"
            elif turn_duration > 2.0:  # Stayed stationary too long
                return "completed"
        return "turning"
    
      elif current_phase == "completed":
        # Calculate total shuttle distance
        total_distance = abs(self.max_right_position - self.max_left_position)
        self.current_shuttle_distance = (total_distance / frame_width) * 100
        self.shuttle_runs.append(self.current_shuttle_distance)
        self.shuttle_attempts += 1
        
        # Reset for next shuttle run but keep accumulated stats
        self.shuttle_positions = []
        # DON'T reset direction_changes - keep cumulative count
        self.last_direction_change_pos = None
        self.max_left_position = hip_x_position
        self.max_right_position = hip_x_position
        
        if movement_speed > SPEED_THRESHOLD:
            return "running"
        else:
            return "at_start"
    
      return current_phase
    
    def calculate_distance_score(self):
        """Calculate performance score based on jump distance"""
        if not self.jump_distances:
            return 0
        
        # Define performance benchmarks (relative to frame width %)
        # These can be adjusted based on real-world calibration
        excellent_distance = 25.0  # 25% of frame width
        good_distance = 20.0       # 20% of frame width
        fair_distance = 15.0       # 15% of frame width
        poor_distance = 10.0       # 10% of frame width
        
        best_jump = self.best_distance
        
        if best_jump >= excellent_distance:
            return 95 + min(5, (best_jump - excellent_distance))  # 95-100
        elif best_jump >= good_distance:
            return 80 + (15 * (best_jump - good_distance) / (excellent_distance - good_distance))  # 80-95
        elif best_jump >= fair_distance:
            return 60 + (20 * (best_jump - fair_distance) / (good_distance - fair_distance))  # 60-80
        elif best_jump >= poor_distance:
            return 40 + (20 * (best_jump - poor_distance) / (fair_distance - poor_distance))  # 40-60
        else:
            return max(20, 40 * (best_jump / poor_distance))  # 20-40
    
    def get_distance_classification(self, distance_percent):
        """Classify jump distance performance"""
        if distance_percent >= 25.0:
            return "Excellent", (0, 255, 0)  # Green
        elif distance_percent >= 20.0:
            return "Good", (0, 255, 255)     # Yellow
        elif distance_percent >= 15.0:
            return "Fair", (0, 165, 255)     # Orange
        elif distance_percent >= 10.0:
            return "Poor", (0, 0, 255)       # Red
        else:
            return "Very Poor", (128, 0, 128)  # Purple
        
    def track_jump_trajectory(self, hip_x_position):
      """Track the complete trajectory of the jump for better distance measurement"""
      if not hasattr(self, 'jump_trajectory'):
        self.jump_trajectory = []
    
      if self.rep_phase in ["takeoff", "in_air", "landing"]:
        self.jump_trajectory.append(hip_x_position)
    
    # When jump completes, find the maximum displacement
      if self.rep_phase == "completed" and self.jump_trajectory:
        max_displacement = max(abs(pos - self.baseline_hip_x) for pos in self.jump_trajectory)
        self.jump_trajectory = []  # Reset for next jump
        return max_displacement
    
      return 0

    def calculate_rep_quality(self):
        """Calculate quality score for the current rep based on recent frames"""
        if len(self.metrics_history) < 10:
            return 50  # Not enough data
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 frames
        recent_feedback = self.feedback_history[-10:]
        
        # Count good form frames in recent history
        good_frames = sum(1 for fb in recent_feedback if any(positive in fb.lower() for positive in ["good", "excellent", "perfect", "great", "nice", "complete", "rising", "controlled", "engage", "height"]))
        quality_score = (good_frames / len(recent_feedback)) * 100
        
        return quality_score
    
    def set_exercise_type(self, exercise_type):
        self.exercise_type = exercise_type
        self._load_reference_metrics()
        self.start_time = time.time()
        
        if exercise_type == ExerciseType.STANDING_BROAD_JUMP:
            self.rep_phase = "calibrating"  # Start with calibration
            # Reset broad jump specific variables
            self.jump_distances = []
            self.best_distance = 0
            self.current_jump_distance = 0
            self.jump_attempts = 0
            self.baseline_established = False
            self.calibration_frames = 0
            self.calibration_positions = []

        elif exercise_type == ExerciseType.PLANK_HOLD:
            self.rep_phase = "not_holding"  # Start not holding
            self.plank_start_time = None
        elif exercise_type == ExerciseType.SITUPS:
            self.rep_phase = "at_bottom"  # Start lying down for sit-ups
            # Initialize sit-up specific variables
            self.prev_torso_angle = 25  # Initialize with lying down angle
        
        elif exercise_type == ExerciseType.SHUTTLE_RUN:
          self.rep_phase = "at_start"
    # Reset shuttle run specific variables
          self.shuttle_runs = []
          self.current_shuttle_distance = 0
          self.shuttle_attempts = 0
          self.direction_changes = 0
          self.shuttle_start_time = None
          self.shuttle_positions = []
          self.current_direction = None
          self.last_direction_change_pos = None
          self.turn_start_time = None
          self.running_start_pos = None
          self.max_left_position = None
          self.max_right_position = None
          self.shuttle_run_times = []  # Store time for each shuttle run
          self.last_run_start_time = None
          self.total_shuttle_time = 0
          self.average_shuttle_time = 0
        else:
            self.rep_phase = "at_top"  # Start at top position for other exercises

        

    def _load_reference_metrics(self):
        if self.exercise_type == ExerciseType.SQUATS:
            self.reference_metrics = {
                'knee_angle_range': (70, 120),
                'torso_angle_range': (60, 110),
                'hip_knee_ankle_alignment': 0.8,
                'depth_threshold': 0.5,
                'perfect_knee_angle': 90,
                'perfect_torso_angle': 80
            }
        elif self.exercise_type == ExerciseType.PUSHUPS:
            self.reference_metrics = {
                'elbow_angle_range': (70, 120),
                'shoulder_hip_ankle_alignment': 0.85,
                'depth_threshold': 0.6,
                'perfect_elbow_angle': 90,
                'perfect_alignment': 0.9
            }
        elif self.exercise_type == ExerciseType.VERTICAL_JUMP:
            self.reference_metrics = {
                'prep_knee_angle_range': (90, 130),
                'landing_knee_angle_range': (100, 140),
                'hip_knee_ankle_alignment': 0.8,
                'min_air_time': 0.2,
                'max_prep_time': 2.0,
                'perfect_prep_knee_angle': 110,
                'perfect_landing_knee_angle': 120,
                'symmetry_threshold': 0.9
            }
        elif self.exercise_type == ExerciseType.SITUPS:
            self.reference_metrics = {
        # Torso angle ranges for proper form
        'down_torso_angle_range': (0, 20),     # Lying down position
        'up_torso_angle_range': (60, 90),       # Sitting up position
        
        # Form standards
        'max_knee_bend': 140,                    # Knees should be bent
        'min_knee_bend': 50,                     # But not too much
        'spine_alignment_threshold': 0.40,       # Straight spine during movement
        
        # Movement quality
        'controlled_speed_threshold': 30,        # Frames for controlled movement
        'full_range_motion': True,               # Must go through full range
        
        # Perfect reference values
        'perfect_down_angle': 25,                # Nearly flat
        'perfect_up_angle': 80,                  # Good sit-up position
        'perfect_knee_angle': 90,                # 90-degree knee bend
    }
        elif self.exercise_type == ExerciseType.STANDING_BROAD_JUMP:
          self.reference_metrics = {
        # Preparation and landing form
        'prep_knee_angle_range': (90, 130),
        'landing_knee_angle_range': (80, 160),
        'hip_knee_ankle_alignment': 0.8,
        
        # Distance benchmarks (% of frame width)
        'excellent_distance': 25.0,
        'good_distance': 20.0,
        'fair_distance': 15.0,
        'minimum_distance': 8.0,
        
        # Form standards
        'perfect_prep_knee_angle': 110,
        'perfect_landing_knee_angle': 120,
        'symmetry_threshold': 0.9,
        'max_landing_sway': 0.05,
        
        # Movement thresholds
        'min_horizontal_movement': 0.05,  # 5% of frame width
        'takeoff_detection_threshold': 0.02  # 2% of frame width
    }
        elif self.exercise_type == ExerciseType.PLANK_HOLD:
             self.reference_metrics = {
        'body_alignment_range': (160, 190),
        'elbow_angle_range': (80, 100),
        'min_hold_time': 10,
        'target_hold_time': 60,
        'perfect_alignment': 180,
        'perfect_elbow_angle': 90,
        'alignment_threshold': 0.9
    }
        elif self.exercise_type == ExerciseType.SHUTTLE_RUN:
          self.reference_metrics = {
        # Movement detection thresholds
        'direction_change_threshold': 0.08,  # 8% of frame width for direction change
        'speed_threshold': 0.02,  # 2% of frame width per frame for movement detection
        'stationary_threshold': 0.01,  # 1% of frame width for stationary detection
        
        # Form standards
        'running_knee_angle_range': (90, 160),
        'turn_knee_angle_range': (80, 140),
        'hip_knee_ankle_alignment': 0.75,
        
        # Performance metrics
        'min_shuttle_distance': 0.15,  # 15% of frame width minimum
        'target_shuttle_distance': 0.25,  # 25% of frame width target
        'max_turn_time': 30,  # Maximum frames for a turn (1 second at 30fps)
        'min_run_time': 15,  # Minimum frames for running phase
        
        # Perfect reference values
        'perfect_running_knee_angle': 125,
        'perfect_turn_knee_angle': 110,
        'symmetry_threshold': 0.85
    }
             
        

    def calculate_angle(self, a, b, c):
        """Calculate angle between three points"""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)

        ba = a - b
        bc = c - b

        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))

        return np.degrees(angle)

    def analyze_squats(self, landmarks, h, w):
        """Analyze squat form with phase-based evaluation and rep counting"""
        feedback = []
        is_correct = True

        # Get key points
        hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                       landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
        knee = np.array([landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * w,
                        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * h])
        ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
        shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * w,
                            landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * h])

        # Calculate angles
        knee_angle = self.calculate_angle(hip, knee, ankle)
        torso_angle = self.calculate_angle(shoulder, hip, knee)
        hip_height = hip[1]  # Y coordinate (higher value = lower position)

        # Detect squat phase and count reps
        new_phase = self.detect_squat_phase(knee_angle, hip_height)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        # Only provide form feedback during key phases
        if self.rep_phase in ["going_down", "at_bottom"]:
            # Check knee angle only during descent and bottom position
            if knee_angle < self.reference_metrics['knee_angle_range'][0]:
                feedback.append("Going too deep! Control the descent.")
                self.form_errors['depth_issues'] += 1
                is_correct = False
            elif knee_angle > 130 and self.rep_phase == "at_bottom":
                feedback.append("Go deeper! Aim for 90 degrees.")
                self.form_errors['depth_issues'] += 1
                is_correct = False

            # Check torso angle during descent
            if torso_angle < self.reference_metrics['torso_angle_range'][0]:
                feedback.append("Chest up! Don't lean forward too much.")
                self.form_errors['torso_lean'] += 1
                is_correct = False

        # Check alignment throughout movement (but more lenient)
        alignment_score = self._check_alignment(hip, knee, ankle)
        if alignment_score < self.reference_metrics['hip_knee_ankle_alignment'] and self.rep_phase != "at_top":
            feedback.append("Keep knees aligned with toes.")
            self.form_errors['knee_alignment'] += 1
            is_correct = False

        # Phase-specific feedback
        if phase_changed:
            if self.rep_phase == "going_down":
                feedback.append("Descending... keep control!")
            elif self.rep_phase == "at_bottom":
                feedback.append("Good depth! Now drive up!")
            elif self.rep_phase == "going_up":
                feedback.append("Drive through your heels!")
            elif self.rep_phase == "at_top":
                feedback.append("Rep complete! Great job!")

        if is_correct and not feedback:
            feedback.append("Excellent form! Keep going strong!")

        return is_correct, feedback, {
            'knee_angle': knee_angle,
            'torso_angle': torso_angle,
            'alignment_score': alignment_score,
            'phase': self.rep_phase,
            'knee_angle_deviation': abs(knee_angle - self.reference_metrics['perfect_knee_angle']) if self.rep_phase in ["at_bottom", "going_down"] else 0,
            'torso_angle_deviation': abs(torso_angle - self.reference_metrics['perfect_torso_angle']) if self.rep_phase in ["at_bottom", "going_down"] else 0
        }

    def analyze_pushups(self, landmarks, h, w):
        """Analyze pushup form with phase-based evaluation and rep counting"""
        feedback = []
        is_correct = True

        # Get key points
        shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * w,
                            landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * h])
        elbow = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y * h])
        wrist = np.array([landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y * h])
        hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                       landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
        ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])

        # Calculate angles
        elbow_angle = self.calculate_angle(shoulder, elbow, wrist)
        shoulder_height = shoulder[1]

        # Detect pushup phase and count reps
        new_phase = self.detect_pushup_phase(elbow_angle, shoulder_height)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        # Only check form during key phases
        if self.rep_phase in ["going_down", "at_bottom"]:
            # Check elbow angle during descent and bottom position
            if elbow_angle < self.reference_metrics['elbow_angle_range'][0]:
                feedback.append("Great depth! Now push up!")
                # Don't penalize for going too deep in pushups
            elif elbow_angle > 130 and self.rep_phase == "at_bottom":
                feedback.append("Go lower! Get closer to the ground.")
                self.form_errors['depth_issues'] += 1
                is_correct = False

        # Check body alignment throughout (more lenient)
        alignment_score = self._check_alignment(shoulder, hip, ankle)
        if alignment_score < self.reference_metrics['shoulder_hip_ankle_alignment'] and self.rep_phase != "at_top":
            feedback.append("Keep your body straight! Engage your core.")
            self.form_errors['body_alignment'] += 1
            is_correct = False

        # Phase-specific feedback
        if phase_changed:
            if self.rep_phase == "going_down":
                feedback.append("Descending... control the movement!")
            elif self.rep_phase == "at_bottom":
                feedback.append("Good depth! Drive up!")
            elif self.rep_phase == "going_up":
                feedback.append("Push through! Almost there!")
            elif self.rep_phase == "at_top":
                feedback.append("Rep complete! Nice work!")

        if is_correct and not feedback:
            feedback.append("Perfect form! Keep it up!")

        return is_correct, feedback, {
            'elbow_angle': elbow_angle,
            'alignment_score': alignment_score,
            'phase': self.rep_phase,
            'elbow_angle_deviation': abs(elbow_angle - self.reference_metrics['perfect_elbow_angle']) if self.rep_phase in ["at_bottom", "going_down"] else 0,
            'alignment_deviation': abs(alignment_score - self.reference_metrics['perfect_alignment']) if self.rep_phase != "at_top" else 0
        }

    def analyze_situps(self, landmarks, h, w):
        """Analyze sit-up form with phase-based evaluation and rep counting"""
        feedback = []
        is_correct = True

        # Ensure reference metrics are loaded
        if not hasattr(self, 'reference_metrics') or not self.reference_metrics:
            self._load_reference_metrics()

        # Get key points for sit-up analysis
        shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * w,
                            landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * h])
        hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                       landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
        knee = np.array([landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * w,
                        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * h])
        ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
        
        # For torso angle, we need a reference point - use a vertical line from hip
        # Create virtual point directly above hip for torso angle calculation
        # Calculate torso angle relative to horizontal ground plane
        horizontal_point = np.array([hip[0] + 100, hip[1]])  # Horizontal reference
        torso_angle = self.calculate_angle(horizontal_point, hip, shoulder)
        knee_angle = self.calculate_angle(hip, knee, ankle)

        # Calculate torso angle as angle from horizontal (0 degrees = lying flat, 90 degrees = sitting up)
        torso_vector = shoulder - hip
        horizontal_vector = np.array([100, 0])  # Pure horizontal vector
# Calculate angle between torso and horizontal
        dot_product = np.dot(torso_vector, horizontal_vector)
        torso_magnitude = np.linalg.norm(torso_vector)
        horizontal_magnitude = np.linalg.norm(horizontal_vector)
        if torso_magnitude > 0:
            cos_angle = dot_product / (torso_magnitude * horizontal_magnitude)
            torso_angle = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
    # Adjust angle based on vertical position (shoulder above or below hip)
            if shoulder[1] < hip[1]:  # Shoulder above hip (sitting up)
               torso_angle = torso_angle
            else:  # Shoulder below hip (lying down)
               torso_angle = 180 - torso_angle
    # Normalize to 0-90 range where 0=lying flat, 90=sitting up
            if torso_angle > 90:
               torso_angle = 180 - torso_angle
        else:
           torso_angle = 0
        
        # Get heights for phase detection
        shoulder_height = shoulder[1]
        hip_height = hip[1]

        # Detect sit-up phase and count reps
        new_phase = self.detect_situp_phase(torso_angle, shoulder_height, hip_height)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        # Form analysis during different phases
        if self.rep_phase in ["going_up", "at_top"]:
            # Check if knees are properly bent
            if knee_angle < self.reference_metrics.get('min_knee_bend', 50):
                feedback.append("Bend your knees more! Keep feet flat.")
                self.form_errors['knee_alignment'] += 1
                is_correct = False
            elif knee_angle > self.reference_metrics.get('max_knee_bend', 140):
                feedback.append("Don't bend knees too much - around 90 degrees is ideal.")
                self.form_errors['knee_alignment'] += 1
                is_correct = False
            
            # Check torso angle during upward movement
            up_range = self.reference_metrics.get('up_torso_angle_range', (60, 90))
            if self.rep_phase == "at_top" and torso_angle < up_range[0]:
                feedback.append("Come up higher! Get closer to your knees.")
                self.form_errors['depth_issues'] += 1
                is_correct = False
            elif self.rep_phase == "at_top" and torso_angle > up_range[1]:
                feedback.append("Don't lean too far forward. Controlled movement!")
                self.form_errors['torso_lean'] += 1
                is_correct = False

        elif self.rep_phase in ["going_down", "at_bottom"]:
            # Check controlled descent
            down_range = self.reference_metrics.get('down_torso_angle_range', (0, 40))
            if self.rep_phase == "at_bottom" and torso_angle > down_range[1]:
                feedback.append("Go down further! Shoulders should touch the ground.")
                self.form_errors['depth_issues'] += 1
                is_correct = False
            elif self.rep_phase == "at_bottom" and torso_angle < down_range[0]:
                feedback.append("Perfect range of motion!")
                # This is actually good form

        # Check spine alignment (shoulder-hip alignment during movement)
        spine_alignment = self._check_alignment(shoulder, hip, np.array([hip[0], hip[1] + 50]))
        spine_threshold = self.reference_metrics.get('spine_alignment_threshold', 0.40)
        if spine_alignment < spine_threshold and self.rep_phase not in ["at_bottom"]:
            feedback.append("Keep your spine straight! Don't twist or curve.")
            self.form_errors['body_alignment'] += 1
            is_correct = False

        # Phase-specific feedback
        if phase_changed:
            if self.rep_phase == "going_up":
                feedback.append("Rising up... engage your core!")
            elif self.rep_phase == "at_top":
                feedback.append("Good height! Now controlled descent.")
            elif self.rep_phase == "going_down":
                feedback.append("Controlled descent... don't drop!")
            elif self.rep_phase == "at_bottom":
                feedback.append("Rep complete! Great work!")

        # General form reminders
        if is_correct and not feedback:
            feedback.append("Excellent sit-up form! Keep it controlled!")

        # Additional checks for common sit-up mistakes
        # Check if movement is too fast (jerky motion)
        if hasattr(self, 'prev_torso_angle'):
            angle_change = abs(torso_angle - self.prev_torso_angle)
            if angle_change > 20:  # More than 20 degrees change in one frame
                feedback.append("Slow down! Control the movement.")
                self.form_errors['body_alignment'] += 1
                is_correct = False
        
        self.prev_torso_angle = torso_angle

        return is_correct, feedback, {
            'torso_angle': torso_angle,
            'knee_angle': knee_angle,
            'spine_alignment': spine_alignment,
            'shoulder_hip_diff': hip_height - shoulder_height,
            'phase': self.rep_phase,
            'torso_angle_deviation': abs(torso_angle - self.reference_metrics.get('perfect_up_angle', 80)) if self.rep_phase == "at_top" else abs(torso_angle - self.reference_metrics.get('perfect_down_angle', 25)) if self.rep_phase == "at_bottom" else 0,
            'knee_angle_deviation': abs(knee_angle - self.reference_metrics.get('perfect_knee_angle', 90))
        }
    def analyze_vertical_jump(self, landmarks, h, w):
        """Analyze vertical jump form with phase-based evaluation and rep counting"""
        feedback = []
        is_correct = True

        # Get key points for both sides to check symmetry
        left_hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                            landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
        right_hip = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x * w,
                             landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y * h])
        left_knee = np.array([landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * w,
                             landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * h])
        right_knee = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x * w,
                              landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y * h])
        left_ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                              landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
        right_ankle = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x * w,
                               landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * h])
        left_shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * w,
                                 landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * h])

        # Calculate average hip height for jump tracking
        avg_hip_height = (left_hip[1] + right_hip[1]) / 2
        avg_ankle_height = (left_ankle[1] + right_ankle[1]) / 2
        
        # Calculate knee angles for both legs
        left_knee_angle = self.calculate_angle(left_hip, left_knee, left_ankle)
        right_knee_angle = self.calculate_angle(right_hip, right_knee, right_ankle)
        avg_knee_angle = (left_knee_angle + right_knee_angle) / 2

        # Detect jump phase and count reps
        new_phase = self.detect_jump_phase(avg_hip_height, avg_knee_angle, avg_ankle_height)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        # Phase-specific form analysis
        if self.rep_phase == "preparing":
            # Check preparation form
            if avg_knee_angle < self.reference_metrics['prep_knee_angle_range'][0]:
                feedback.append("Don't squat too deep in preparation!")
                self.form_errors['depth_issues'] += 1
                is_correct = False
            elif avg_knee_angle > self.reference_metrics['prep_knee_angle_range'][1]:
                feedback.append("Bend your knees more for better power!")
                self.form_errors['takeoff_form'] += 1
                is_correct = False
            
            # Check symmetry
            knee_angle_diff = abs(left_knee_angle - right_knee_angle)
            if knee_angle_diff > 15:  # More than 15 degrees difference
                feedback.append("Keep both legs symmetrical!")
                self.form_errors['jump_asymmetry'] += 1
                is_correct = False

        elif self.rep_phase == "landing":
            # Check landing form
            if avg_knee_angle < self.reference_metrics['landing_knee_angle_range'][0]:
                feedback.append("Bend your knees more on landing for safety!")
                self.form_errors['landing_form'] += 1
                is_correct = False
            elif avg_knee_angle > self.reference_metrics['landing_knee_angle_range'][1]:
                feedback.append("Don't land too stiff! Absorb the impact!")
                self.form_errors['landing_form'] += 1
                is_correct = False
            
            # Check landing symmetry
            knee_angle_diff = abs(left_knee_angle - right_knee_angle)
            if knee_angle_diff > 20:  # More lenient on landing
                feedback.append("Try to land evenly on both feet!")
                self.form_errors['jump_asymmetry'] += 1
                is_correct = False

        # Check overall alignment
        left_alignment = self._check_alignment(left_hip, left_knee, left_ankle)
        right_alignment = self._check_alignment(right_hip, right_knee, right_ankle)
        avg_alignment = (left_alignment + right_alignment) / 2
        
        if avg_alignment < self.reference_metrics['hip_knee_ankle_alignment'] and self.rep_phase != "in_air":
            feedback.append("Keep your knees aligned with your toes!")
            self.form_errors['knee_alignment'] += 1
            is_correct = False

        # Phase-specific feedback
        if phase_changed:
            if self.rep_phase == "preparing":
                feedback.append("Good preparation! Get ready to explode up!")
            elif self.rep_phase == "takeoff":
                feedback.append("Drive up with power!")
            elif self.rep_phase == "in_air":
                feedback.append("Great jump! Prepare for landing!")
            elif self.rep_phase == "landing":
                feedback.append("Jump complete! Nice work!")
            elif self.rep_phase == "at_baseline":
                feedback.append("Ready for next jump!")

        if is_correct and not feedback:
            feedback.append("Perfect jump form!")

        # Calculate jump height estimate (relative)
        jump_height_relative = 0
        if hasattr(self, 'baseline_hip_height') and self.baseline_hip_height > 0:
            jump_height_relative = max(0, (self.baseline_hip_height - avg_hip_height) / self.baseline_hip_height * 100)

        return is_correct, feedback, {
            'left_knee_angle': left_knee_angle,
            'right_knee_angle': right_knee_angle,
            'avg_knee_angle': avg_knee_angle,
            'left_alignment': left_alignment,
            'right_alignment': right_alignment,
            'avg_alignment': avg_alignment,
            'phase': self.rep_phase,
            'jump_height_relative': jump_height_relative,
            'knee_asymmetry': abs(left_knee_angle - right_knee_angle),
            'knee_angle_deviation': abs(avg_knee_angle - self.reference_metrics.get('perfect_prep_knee_angle', 110)) if self.rep_phase == "preparing" else abs(avg_knee_angle - self.reference_metrics.get('perfect_landing_knee_angle', 120)) if self.rep_phase == "landing" else 0
        }
    
    def analyze_standing_broad_jump(self, landmarks, h, w):
        """Analyze standing broad jump form with distance-focused evaluation"""
        feedback = []
        is_correct = True

        # Get key points for both sides to check symmetry
        left_hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                            landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
        right_hip = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x * w,
                             landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y * h])
        left_knee = np.array([landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * w,
                             landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * h])
        right_knee = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x * w,
                              landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y * h])
        left_ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                              landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
        right_ankle = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x * w,
                               landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * h])

        # Calculate averages for tracking
        avg_hip_x = (left_hip[0] + right_hip[0]) / 2
        avg_ankle_height = (left_ankle[1] + right_ankle[1]) / 2
        
        # Calculate knee angles for both legs
        left_knee_angle = self.calculate_angle(left_hip, left_knee, left_ankle)
        right_knee_angle = self.calculate_angle(right_hip, right_knee, right_ankle)
        avg_knee_angle = (left_knee_angle + right_knee_angle) / 2

        # Detect broad jump phase and track distance
        new_phase = self.detect_broad_jump_phase(avg_hip_x, avg_knee_angle, avg_ankle_height, w)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        # Phase-specific form analysis and feedback
        if self.rep_phase == "calibrating":
            feedback.append("Establishing baseline position... Stay still!")
            
        elif self.rep_phase == "preparing":
            # Check preparation form
            if avg_knee_angle < self.reference_metrics['prep_knee_angle_range'][0]:
                feedback.append("Don't squat too deep! Focus on explosive power.")
                self.form_errors['depth_issues'] += 1
                is_correct = False
            elif avg_knee_angle > self.reference_metrics['prep_knee_angle_range'][1]:
                feedback.append("Bend your knees more for maximum power!")
                self.form_errors['takeoff_form'] += 1
                is_correct = False
            else:
                feedback.append("Good preparation! Get ready to explode forward!")
            
            # Check symmetry
            knee_angle_diff = abs(left_knee_angle - right_knee_angle)
            if knee_angle_diff > 15:
                feedback.append("Keep both legs symmetrical for balanced takeoff!")
                self.form_errors['jump_asymmetry'] += 1
                is_correct = False

        elif self.rep_phase == "takeoff":
            feedback.append("Drive forward with maximum power!")
            
        elif self.rep_phase == "in_air":
            feedback.append("Great jump! Prepare for safe landing!")
            
        elif self.rep_phase == "landing":
            # Check landing form
            if avg_knee_angle < self.reference_metrics['landing_knee_angle_range'][0]:
                feedback.append("Bend your knees more on landing to absorb impact!")
                self.form_errors['landing_form'] += 1
                is_correct = False
            elif avg_knee_angle > self.reference_metrics['landing_knee_angle_range'][1]:
                feedback.append("Don't land too stiff! Absorb the landing!")
                self.form_errors['landing_form'] += 1
                is_correct = False
            else:
                feedback.append("Good landing form! Absorbing the impact well.")
            
            # Check landing stability
            hip_sway = abs(left_hip[0] - right_hip[0]) / w  # Normalized sway
            if hip_sway > self.reference_metrics['max_landing_sway']:
                feedback.append("Try to land more balanced and stable!")
                self.form_errors['landing_form'] += 1
                is_correct = False
                
        elif self.rep_phase == "completed":
            # Provide distance feedback
            distance_class, distance_color = self.get_distance_classification(self.current_jump_distance)
            feedback.append(f"Jump complete! Distance: {distance_class} ({self.current_jump_distance:.1f}%)")
            
        elif self.rep_phase == "at_baseline":
            if self.jump_attempts > 0:
                feedback.append(f"Ready for next jump! Best so far: {self.best_distance:.1f}%")
            else:
                feedback.append("Ready to jump! Take your time to prepare.")

        # Check overall alignment during movement phases
        left_alignment = self._check_alignment(left_hip, left_knee, left_ankle)
        right_alignment = self._check_alignment(right_hip, right_knee, right_ankle)
        avg_alignment = (left_alignment + right_alignment) / 2
        
        if avg_alignment < self.reference_metrics['hip_knee_ankle_alignment'] and self.rep_phase not in ["in_air", "calibrating"]:
            feedback.append("Keep your knees aligned with your toes!")
            self.form_errors['knee_alignment'] += 1
            is_correct = False

        if is_correct and len(feedback) == 0:
           feedback.append("Good form!")
        elif is_correct:
    # Don't override existing positive feedback
           pass

        # Calculate distance metrics
        horizontal_displacement = 0
        if hasattr(self, 'baseline_hip_x') and self.baseline_hip_x is not None:
            horizontal_displacement = abs(avg_hip_x - self.baseline_hip_x) / w * 100

        return is_correct, feedback, {
            'left_knee_angle': left_knee_angle,
            'right_knee_angle': right_knee_angle,
            'avg_knee_angle': avg_knee_angle,
            'left_alignment': left_alignment,
            'right_alignment': right_alignment,
            'avg_alignment': avg_alignment,
            'phase': self.rep_phase,
            'current_displacement': horizontal_displacement,
            'current_jump_distance': self.current_jump_distance,
            'best_distance': self.best_distance,
            'attempts': self.jump_attempts,
            'knee_asymmetry': abs(left_knee_angle - right_knee_angle),
            'knee_angle_deviation': abs(avg_knee_angle - self.reference_metrics.get('perfect_prep_knee_angle', 110)) if self.rep_phase == "preparing" else abs(avg_knee_angle - self.reference_metrics.get('perfect_landing_knee_angle', 120)) if self.rep_phase == "landing" else 0
        }
    

    def analyze_plank_hold(self, landmarks, h, w):
      """Analyze plank hold form with duration tracking"""
      feedback = []
      is_correct = True

    # Get key points
      left_shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * w,
                             landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * h])
      right_shoulder = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x * w,
                              landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y * h])
      left_elbow = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x * w,
                          landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y * h])
      right_elbow = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x * w,
                           landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y * h])
      left_hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                        landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
      right_hip = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x * w,
                         landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y * h])
      left_ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                          landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
      right_ankle = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x * w,
                           landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * h])
      left_wrist = np.array([landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x * w,
                      landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y * h])
      right_wrist = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x * w,
                       landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y * h])

    # Calculate averages
      avg_shoulder = (left_shoulder + right_shoulder) / 2
      avg_hip = (left_hip + right_hip) / 2
      avg_ankle = (left_ankle + right_ankle) / 2
      avg_elbow = (left_elbow + right_elbow) / 2

    # Calculate angles
      body_alignment_angle = self.calculate_angle(avg_shoulder, avg_hip, avg_ankle)
      left_elbow_angle = self.calculate_angle(left_shoulder, left_elbow, left_wrist)
      right_elbow_angle = self.calculate_angle(right_shoulder, right_elbow, right_wrist)
      avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2

    # Calculate hold duration
      current_time = time.time()
      if hasattr(self, 'plank_start_time') and self.plank_start_time:
        hold_duration = current_time - self.plank_start_time
      else:
        hold_duration = 0

    # Detect plank phase
      new_phase = self.detect_plank_phase(body_alignment_angle, avg_elbow_angle, hold_duration)
      phase_changed = new_phase != self.rep_phase
      self.rep_phase = new_phase

    # Form analysis
      if body_alignment_angle < 150:
        feedback.append("Keep your body straight! Don't let hips sag.")
        self.form_errors['body_alignment'] += 1
        is_correct = False
      elif body_alignment_angle > 200:
        feedback.append("Don't pike up! Keep body in straight line.")
        self.form_errors['body_alignment'] += 1
        is_correct = False

      if avg_elbow_angle < 60:
        feedback.append("Keep elbows at 90 degrees!")
        self.form_errors['elbow_position'] += 1
        is_correct = False
      elif avg_elbow_angle > 130:
        feedback.append("Don't lock elbows! Keep 90-degree bend.")
        self.form_errors['elbow_position'] += 1
        is_correct = False

    # Phase-specific feedback
      if self.rep_phase == "holding":
        if hold_duration > 0:
            feedback.append(f"Good hold! Duration: {hold_duration:.1f}s")
        else:
            feedback.append("Hold the position! Keep core engaged!")
      elif self.rep_phase == "not_holding":
        feedback.append("Get into plank position. Keep body straight!")
        self.plank_start_time = None

      if is_correct and self.rep_phase != "holding":
        feedback.append("Perfect form! Now hold the position!")

      return is_correct, feedback, {
        'body_alignment_angle': body_alignment_angle,
        'avg_elbow_angle': avg_elbow_angle,
        'hold_duration': hold_duration,
        'phase': self.rep_phase,
        'alignment_deviation': abs(body_alignment_angle - 180) if self.rep_phase == "holding" else 0,
        'elbow_deviation': abs(avg_elbow_angle - 90) if self.rep_phase == "holding" else 0
    }

    def analyze_shuttle_run(self, landmarks, h, w):
      """Analyze shuttle run form with direction change and distance tracking"""
      feedback = []
      is_correct = True
    
    # Get key points
      left_hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                        landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
      right_hip = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x * w,
                         landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y * h])
      left_knee = np.array([landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * h])
      right_knee = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x * w,
                          landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y * h])
      left_ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                          landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
      right_ankle = np.array([landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x * w,
                           landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * h])
    
    # Calculate averages
      avg_hip_x = (left_hip[0] + right_hip[0]) / 2
      left_knee_angle = self.calculate_angle(left_hip, left_knee, left_ankle)
      right_knee_angle = self.calculate_angle(right_hip, right_knee, right_ankle)
      avg_knee_angle = (left_knee_angle + right_knee_angle) / 2
    
    # Track position history for movement detection
      self.shuttle_positions.append(avg_hip_x)
      if len(self.shuttle_positions) > 10:  # Keep last 10 positions
        self.shuttle_positions.pop(0)
    
    # Calculate movement speed
      movement_speed = 0
      if len(self.shuttle_positions) >= 3:
        movement_speed = abs(self.shuttle_positions[-1] - self.shuttle_positions[-3]) / 2
    
    # Detect shuttle run phase
      new_phase = self.detect_shuttle_run_phase(avg_hip_x, avg_knee_angle, movement_speed, w)
      phase_changed = new_phase != self.rep_phase
      self.rep_phase = new_phase
    
    # Phase-specific form analysis
      if self.rep_phase == "running":
        # Check running form
        running_range = self.reference_metrics['running_knee_angle_range']
        if avg_knee_angle < running_range[0]:
            feedback.append("Lift your knees higher while running!")
            self.form_errors['knee_alignment'] += 1
            is_correct = False
        elif avg_knee_angle > running_range[1]:
            feedback.append("Don't overstride! Keep knees under control.")
            self.form_errors['knee_alignment'] += 1
            is_correct = False
        else:
            feedback.append("Good running form! Keep the pace up!")
    
      elif self.rep_phase == "turning":
        # Check turning form
        turn_range = self.reference_metrics['turn_knee_angle_range']
        if avg_knee_angle < turn_range[0]:
            feedback.append("Bend knees more during turns for stability!")
            self.form_errors['depth_issues'] += 1
            is_correct = False
        elif avg_knee_angle > turn_range[1]:
            feedback.append("Lower your center of gravity in turns!")
            self.form_errors['depth_issues'] += 1
            is_correct = False
        else:
            feedback.append("Good turning technique! Quick direction change!")
    
      elif self.rep_phase == "at_start":
        feedback.append("Ready to start shuttle run! Sprint to one side!")
    
      elif self.rep_phase == "completed":
        feedback.append(f"Shuttle run complete! Distance: {self.current_shuttle_distance:.1f}%")
    
    # Check leg symmetry during movement
      knee_asymmetry = abs(left_knee_angle - right_knee_angle)
      if knee_asymmetry > 20 and self.rep_phase == "running":
        feedback.append("Keep both legs working equally!")
        self.form_errors['jump_asymmetry'] += 1
        is_correct = False
    
    # Check alignment
      left_alignment = self._check_alignment(left_hip, left_knee, left_ankle)
      right_alignment = self._check_alignment(right_hip, right_knee, right_ankle)
      avg_alignment = (left_alignment + right_alignment) / 2
    
      if avg_alignment < self.reference_metrics['hip_knee_ankle_alignment']:
        feedback.append("Keep knees aligned with your direction of movement!")
        self.form_errors['knee_alignment'] += 1
        is_correct = False
    
    # Phase change feedback
      if phase_changed:
        if self.rep_phase == "running":
            feedback.append("Sprinting! Drive with your arms!")
        elif self.rep_phase == "turning":
            feedback.append("Quick turn! Plant and pivot!")
    
      if is_correct and not feedback:
        feedback.append("Excellent shuttle run form!")
    
    # Calculate total distance covered
      total_distance = 0
      if hasattr(self, 'max_left_position') and hasattr(self, 'max_right_position'):
        total_distance = abs(self.max_right_position - self.max_left_position) / w * 100
    
      return is_correct, feedback, {
        'left_knee_angle': left_knee_angle,
        'right_knee_angle': right_knee_angle,
        'avg_knee_angle': avg_knee_angle,
        'left_alignment': left_alignment,
        'right_alignment': right_alignment,
        'avg_alignment': avg_alignment,
        'phase': self.rep_phase,
        'movement_speed': movement_speed,
        'direction_changes': self.direction_changes,
        'total_distance': total_distance,
        'current_direction': self.current_direction if hasattr(self, 'current_direction') else 'none',
        'knee_asymmetry': knee_asymmetry,
        'knee_angle_deviation': abs(avg_knee_angle - self.reference_metrics.get('perfect_running_knee_angle', 125)) if self.rep_phase == "running" else abs(avg_knee_angle - self.reference_metrics.get('perfect_turn_knee_angle', 110)) if self.rep_phase == "turning" else 0,
        # Add these new time metrics:
        'average_run_time': sum(self.shuttle_run_times) / len(self.shuttle_run_times) if hasattr(self, 'shuttle_run_times') and self.shuttle_run_times else 0,
        'total_runs': len(self.shuttle_run_times) if hasattr(self, 'shuttle_run_times') else 0,
        'current_run_time': time.time() - self.last_run_start_time if hasattr(self, 'last_run_start_time') and self.last_run_start_time else 0

    }

    def _check_alignment(self, a, b, c):
        """Check how well three points are aligned"""
        ab = b - a
        bc = c - b

        dot_product = np.dot(ab, bc)
        mag_ab = np.linalg.norm(ab)
        mag_bc = np.linalg.norm(bc)

        if mag_ab == 0 or mag_bc == 0:
            return 0
        cosine_angle = dot_product / (mag_ab * mag_bc)
        alignment_score = (cosine_angle + 1) / 2
        return alignment_score

    def calculate_overall_score(self):
        """Calculate overall performance score - for broad jump, heavily weight distance"""
        if self.exercise_type == ExerciseType.STANDING_BROAD_JUMP:
            return self.calculate_distance_score()
        
        # Original scoring for other exercises
        if not self.metrics_history:
            return 50  # Base score instead of 0
        
        # Calculate form accuracy with better weighting
        correct_frames = sum(1 for fb in self.feedback_history if any(positive in fb.lower() for positive in ["good", "excellent", "perfect", "great", "nice", "ready", "complete", "drive", "explode"]))
        total_frames = len(self.feedback_history)
        form_accuracy = (correct_frames / total_frames) if total_frames > 0 else 0
        
        # Calculate rep quality average
        rep_quality_avg = sum(self.rep_quality_scores) / len(self.rep_quality_scores) if self.rep_quality_scores else 50
        
        # Calculate deviation score with better normalization
        total_deviation = 0
        deviation_count = 0
        
        for metrics in self.metrics_history:
            if metrics:
                for key, value in metrics.items():
                    if 'deviation' in key and value > 0:  # Only count actual deviations
                        total_deviation += min(value, 45)  # Cap extreme deviations
                        deviation_count += 1
        
        avg_deviation = total_deviation / deviation_count if deviation_count > 0 else 0
        deviation_score = max(0, 1 - (avg_deviation / 45))  # More forgiving normalization
        
        # Improved scoring formula
        base_score = 60  # Start with a base score
        form_bonus = form_accuracy * 25  # Up to 25 points for good form
        rep_bonus = (rep_quality_avg / 100) * 10  # Up to 10 points for rep quality
        precision_bonus = deviation_score * 5  # Up to 5 points for precision
        
        overall_score = base_score + form_bonus + rep_bonus + precision_bonus
        
        # Bonus for completing reps
        if self.rep_count > 0:
            rep_bonus = min(self.rep_count * 2, 10)  # 2 points per rep, max 10
            overall_score += rep_bonus
        
        return min(100, max(30, overall_score))  # Score between 30-100

    def process_frame(self, image):
        """Process a single frame for exercise analysis"""
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)

        h, w, _ = image.shape
        feedback_text = ""
        metrics = {}

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                image,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
            )

            landmarks = results.pose_landmarks.landmark

            if self.exercise_type == ExerciseType.SQUATS:
                self.is_correct_form, feedback_list, metrics = self.analyze_squats(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"

            elif self.exercise_type == ExerciseType.PUSHUPS:
                self.is_correct_form, feedback_list, metrics = self.analyze_pushups(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"

            elif self.exercise_type == ExerciseType.SITUPS:
                self.is_correct_form, feedback_list, metrics = self.analyze_situps(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"

            elif self.exercise_type == ExerciseType.VERTICAL_JUMP:
                self.is_correct_form, feedback_list, metrics = self.analyze_vertical_jump(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"

            elif self.exercise_type == ExerciseType.STANDING_BROAD_JUMP:
                self.is_correct_form, feedback_list, metrics = self.analyze_standing_broad_jump(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"
            elif self.exercise_type == ExerciseType.PLANK_HOLD:
                self.is_correct_form, feedback_list, metrics = self.analyze_plank_hold(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"

            elif self.exercise_type == ExerciseType.SHUTTLE_RUN:
                self.is_correct_form, feedback_list, metrics = self.analyze_shuttle_run(landmarks, h, w)
                feedback_text = " | ".join(feedback_list) if feedback_list else "Good form!"
            
            self.feedback_history.append(feedback_text)
            self.metrics_history.append(metrics)

            # Display metrics - customize for broad jump
            y_offset = 30
            if self.exercise_type == ExerciseType.STANDING_BROAD_JUMP:
                # Special display for broad jump metrics
                cv2.putText(image, f"Phase: {self.rep_phase.replace('_', ' ').title()}", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y_offset += 25
                
                if hasattr(self, 'baseline_established') and self.baseline_established:
                    cv2.putText(image, f"Current Distance: {metrics.get('current_displacement', 0):.1f}%", (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    y_offset += 22
                    
                    if self.best_distance > 0:
                        distance_class, distance_color = self.get_distance_classification(self.best_distance)
                       
                        cv2.putText(image, f"Best {self.best_distance:.1f}% ({distance_class})", (10, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, distance_color, 2)
                        y_offset += 22

                        cv2.putText(image, f"Rating: {distance_class}", (10, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, distance_color, 2)
                        y_offset += 22
                    
                    cv2.putText(image, f"Attempts: {self.jump_attempts}", (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    y_offset += 22
                    
                    # Show knee angles for form
                    cv2.putText(image, f"Knee Angle: {metrics.get('avg_knee_angle', 0):.0f}", (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    y_offset += 22
                    
                else:
                    cv2.putText(image, f"Calibrating... {self.calibration_frames}/30", (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                    y_offset += 22
                    
            elif self.exercise_type == ExerciseType.SHUTTLE_RUN:
    # Special display for shuttle run metrics
               cv2.putText(image, f"Phase: {self.rep_phase.replace('_', ' ').title()}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
               y_offset += 25
               
               current_dir = metrics.get('current_direction') or 'none'
               cv2.putText(image, f"Direction: {current_dir.title()}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
               y_offset += 22
    
               cv2.putText(image, f"Direction Changes: {metrics.get('direction_changes', 0)}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
               y_offset += 22

               cv2.putText(image, f"Move Speed: {metrics.get('movement_speed', 0):.3f}", (10, y_offset),
                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
               y_offset += 20
    
               cv2.putText(image, f"Total Distance: {metrics.get('total_distance', 0):.1f}%", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
               y_offset += 22

               cv2.putText(image, f"Shuttle Runs: {metrics.get('total_runs', 0)}", (10, y_offset),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
               y_offset += 22

               if metrics.get('average_run_time', 0) > 0:
                  cv2.putText(image, f"Avg Run Time: {metrics.get('average_run_time', 0):.1f}s", (10, y_offset),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                  y_offset += 22

               if self.rep_phase == "running" and metrics.get('current_run_time', 0) > 0:
                  cv2.putText(image, f"Current Run: {metrics.get('current_run_time', 0):.1f}s", (10, y_offset),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                  y_offset += 22
    
    
               cv2.putText(image, f"Knee Angle: {metrics.get('avg_knee_angle', 0):.0f}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
               y_offset += 22

            else:
                # Standard display for other exercises
                for key, value in metrics.items():
                    if not 'deviation' in key and key not in ['phase', 'attempts', 'current_displacement', 'current_jump_distance', 'best_distance']:
                        if isinstance(value, (int, float)):
                            cv2.putText(image, f"{key}: {value:.1f}", (10, y_offset),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        else:
                            cv2.putText(image, f"{key}: {value}", (10, y_offset),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        y_offset += 25

                # Display rep count for rep-based exercises
                cv2.putText(image, f"Reps: {self.rep_count}", (w - 150, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)

            # Display feedback
            color = (0, 255, 0) if self.is_correct_form else (0, 0, 255)
            # Split long feedback text
            max_chars = 80
            if len(feedback_text) > max_chars:
                words = feedback_text.split(' ')
                line1 = ' '.join(words[:len(words)//2])
                line2 = ' '.join(words[len(words)//2:])
                cv2.putText(image, line1, (10, h - 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.putText(image, line2, (10, h - 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            else:
                cv2.putText(image, feedback_text, (10, h - 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Display current score
            current_score = self.calculate_overall_score()
            score_label = "Distance Score" if self.exercise_type == ExerciseType.STANDING_BROAD_JUMP else "Form Score"
            cv2.putText(image, f"{score_label}: {current_score:.0f}/100", (w - 220, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        return image, feedback_text, metrics

    def get_ai_summary(self, report_data):
        try:
            hf_token = "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"
            if hf_token:
                summary = self._try_huggingface_api(report_data, hf_token)
                if summary:
                    return summary
            return self._generate_enhanced_rule_based_summary(report_data)
        except Exception as e:
            print(f"AI API error: {e}")
            return self._generate_enhanced_rule_based_summary(report_data)

    def _try_huggingface_api(self, report_data, token):
        try:
            api_url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-large"
            headers = {"Authorization": f"Bearer {token}"}

            exercise_name = self.exercise_type.name.replace('_', ' ').title()
            prompt = f"""
Generate a professional fitness analysis summary:

Exercise: {exercise_name}
Score: {report_data['score']:.1f}/100
Form Accuracy: {report_data['form_accuracy']:.1f}%
Key Issues: {', '.join(report_data['common_feedback'][:3]) if report_data['common_feedback'] else 'None identified'}

Provide:
1. A brief performance summary
2. 2-3 key findings
3. 2-3 specific recommendations for improvement

Keep response concise and professional.
"""
            payload = {"inputs": prompt, "parameters": {"max_length": 200}}
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            print("Response",response)
            result = response.json()           # convert response to JSON
            print("JSON Result:", result)   

            if response.status_code == 200:
                result = response.json()
                return self._parse_ai_response(result)
            else:
                print(f"Hugging Face API returned {response.status_code}: {response.text}")

        except Exception as e:
            print(f"Hugging Face API failed: {e}")
        return None

    def _parse_ai_response(self, generated_text):
        try:
            # Limit summary to first 200 chars
            print(generated_text)
            summary = generated_text[:200] + "..." if len(generated_text) > 200 else generated_text

            # Split lines
            lines = [line.strip("• ").strip() for line in generated_text.split("\n") if line.strip()]
            
            key_findings = []
            recommendations = []

            # Attempt to detect sections
            current_section = None
            for line in lines:
                lower = line.lower()
                if "key findings" in lower:
                    current_section = "key_findings"
                    continue
                elif "recommendations" in lower:
                    current_section = "recommendations"
                    continue

                if current_section == "key_findings":
                    key_findings.append(line)
                elif current_section == "recommendations":
                    recommendations.append(line)

            # If headings missing, split by bullets or numbers
            if not key_findings:
                key_findings = [line for line in lines if line and line[0].isdigit() or line.startswith("•")][:3]
            if not recommendations:
                recommendations = [line for line in lines if line and line[0].isdigit() or line.startswith("•")][-3:]

            # Final fallback
            if not key_findings:
                key_findings = ["Form inconsistencies detected", "Performance analysis completed"]
            if not recommendations:
                recommendations = ["Follow suggested improvements", "Practice with guided feedback"]

            return {
                "summary": summary,
                "key_findings": key_findings,
                "recommendations": recommendations
            }

        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return {
                "summary": generated_text,
                "key_findings": ["Form inconsistencies detected"],
                "recommendations": ["Follow suggested improvements"]
            }


    def _generate_enhanced_rule_based_summary(self, report_data):
        exercise_name = self.exercise_type.name.replace('_', ' ').title()
        score = report_data['score']

        if score >= 90:
            performance_level = "Outstanding"
            summary_tone = "demonstrates exceptional form and technique with minimal corrections needed"
        elif score >= 80:
            performance_level = "Excellent"
            summary_tone = "shows excellent form with only minor refinements suggested"
        elif score >= 70:
            performance_level = "Good"
            summary_tone = "displays good technique with some areas needing attention"
        elif score >= 60:
            performance_level = "Satisfactory"
            summary_tone = "shows basic proficiency but requires focused improvement"
        elif score >= 50:
            performance_level = "Fair"
            summary_tone = "demonstrates understanding but needs significant form corrections"
        else:
            performance_level = "Needs Major Improvement"
            summary_tone = "requires comprehensive form training and technique development"

        key_findings = []
        priority_recommendations = []

        total_frames = report_data['total_frames']
        total_feedback_frames = len(self.feedback_history)

        if self.exercise_type == ExerciseType.SQUATS:
            if self.form_errors['knee_alignment'] > total_feedback_frames * 0.2:
                key_findings.append("Frequent knee valgus (inward collapse) during descent.")
                priority_recommendations.append("Focus on pushing knees outward, aligned with toes.")

            if self.form_errors['depth_issues'] > total_feedback_frames * 0.3:
                key_findings.append("Inconsistent squat depth affecting range of motion.")
                priority_recommendations.append("Practice box squats to develop consistent depth.")

            if self.form_errors['torso_lean'] > total_feedback_frames * 0.25:
                key_findings.append("Excessive forward lean compromising spinal alignment.")
                priority_recommendations.append("Strengthen posterior chain and practice goblet squats.")

        elif self.exercise_type == ExerciseType.PUSHUPS:
            if self.form_errors['body_alignment'] > total_feedback_frames * 0.2:
                key_findings.append("Body alignment issues including hip sagging or elevation.")
                priority_recommendations.append("Strengthen core with planks and hollow body holds.")

            if self.form_errors['depth_issues'] > total_feedback_frames * 0.3:
                key_findings.append("Insufficient range of motion in pushup movement.")
                priority_recommendations.append("Use elevation blocks or practice negative pushups.")

            if self.form_errors['elbow_position'] > total_feedback_frames * 0.2:
                key_findings.append("Elbow flaring reducing mechanical efficiency.")
                priority_recommendations.append("Keep elbows at 45-degree angle to torso.")

        if not key_findings:
            if score >= 85:
                key_findings = ["Exceptional form consistency maintained.", "Optimal movement patterns demonstrated.", "Minimal technical corrections needed."]
            else:
                key_findings = ["General form maintenance achieved.", "Minor technique refinements possible.", "Consistent effort demonstrated."]

        if score >= 85:
            priority_recommendations.extend(["Consider progressive overload increases.", "Maintain current excellent form standards."])
        elif score >= 70:
            priority_recommendations.extend(["Focus on form consistency over speed.", "Video review for self-correction."])
        else:
            priority_recommendations.extend(["Slow down movement tempo for better control.", "Consider working with a fitness professional."])

        if self.user_profile.get_bmi() > 0:
            bmi = self.user_profile.get_bmi()
            if bmi > 30:
                priority_recommendations.append("Consider lower impact variations initially.")
            elif bmi < 18.5:
                priority_recommendations.append("Focus on strength building with adequate nutrition.")

        if self.user_profile.age > 50:
            priority_recommendations.append("Emphasize proper warm-up and mobility work.")
        elif self.user_profile.age < 25:
            priority_recommendations.append("Build foundation with perfect form before adding intensity.")

        summary_text = f"""
The user {summary_tone} during the {exercise_name} exercise session.
Performance assessment: {performance_level} ({score:.1f}/100 points).
Form accuracy of {report_data['form_accuracy']:.1f}% was maintained across {total_frames} analyzed frames
over {report_data['duration']:.1f} seconds. Analysis reveals {', '.join(key_findings[:3])}.
Technical proficiency shows {'strong potential' if score >= 60 else 'room for development'}
with targeted improvement focusing on {', '.join([f.split()[0] for f in key_findings[:2]])}.
        """

        return {
            'summary': summary_text.strip(),
            'key_findings': key_findings[:4],
            'recommendations': priority_recommendations[:5]
        }


    async def generate_comprehensive_report(self, analyzed_video_url: str):
        if self.start_time is None:
            duration = 0.0
            print("Warning: Start time not set. Setting duration to 0.")
        else:
            end_time = time.time()
            duration = end_time - self.start_time
        
        correct_frames = sum(1 for fb in self.feedback_history if any(positive in fb.lower() for positive in ["good", "excellent", "perfect", "great", "nice", "complete"]))
        total_frames = len(self.feedback_history)
        form_accuracy = (correct_frames / total_frames * 100) if total_frames > 0 else 0.0
        overall_score = self.calculate_overall_score()
        
        avg_metrics = {}
        if self.metrics_history and any(self.metrics_history):
            valid_metrics = [m for m in self.metrics_history if m]
            if valid_metrics:
                for key in valid_metrics[0].keys():
                    if not 'deviation' in key and key != 'phase':
                        values = [m[key] for m in valid_metrics if key in m and isinstance(m[key], (int, float))]
                        if values:
                            avg_metrics[key] = sum(values) / len(values)
    
        feedback_counter = Counter(self.feedback_history)
        common_feedback = [feedback for feedback, count in feedback_counter.most_common(5)
                        if feedback and not any(positive in feedback.lower() for positive in ["good form", "excellent", "perfect", "great", "nice", "complete"])]
        
        report_data_for_analysis = {
            'score': overall_score,
            'form_accuracy': form_accuracy,
            'duration': duration,
            'total_frames': total_frames,
            'correct_frames': correct_frames,
            'avg_metrics': avg_metrics,
            'common_feedback': common_feedback,
            'rep_count': self.rep_count,
            'form_errors': self.form_errors
        }
        
        # Generate SEPARATE summaries
        rule_based_analysis = self._generate_enhanced_rule_based_summary(report_data_for_analysis)
        ai_analysis = self.get_ai_summary(report_data_for_analysis)
        
        report_json_data = {
            'user_profile': {
                'name': self.user_profile.name,
                'age': self.user_profile.age,
                'height': self.user_profile.height,
                'weight': self.user_profile.weight,
                'bmi': self.user_profile.get_bmi(),
                'fitness_level': self.user_profile.get_fitness_level()
            },
            'exercise_details': {
                'type': self.exercise_type.name,
                'duration': duration,
                'date': datetime.now().isoformat()
            },
            'performance': {
                'overall_score': overall_score,
                'form_accuracy': form_accuracy,
                'grade': ("A" if overall_score >= 85 else "B" if overall_score >= 70 else "C" if overall_score >= 50 else "D"),
                'rep_count': self.rep_count,
            },
            # SEPARATE ANALYSES
            'rule_based_analysis': rule_based_analysis,  # Rule-based summary, findings, recommendations
            'ai_analysis': ai_analysis,  # AI-generated summary, findings, recommendations
            'metrics': avg_metrics,
            'form_errors': self.form_errors,
            'technical_details': {
                'total_frames': total_frames,
                'correct_frames': correct_frames
            },
            'full_feedback_history': self.all_feedback_per_frame,
        }

        report_object_id = ObjectId()
        
        json_filename = f"reports/exercise_report_{report_object_id}.json"
        os.makedirs(os.path.dirname(json_filename), exist_ok=True)
        with open(json_filename, 'w') as f:
            json.dump(report_json_data, f, indent=2)
        print(f"📁 Detailed JSON report saved to: {json_filename}")

        pdf_filename = f"reports/exercise_report_{report_object_id}.pdf"
        if await export_to_pdf(report_json_data, pdf_filename):
            pdf_web_path = f"/reports/exercise_report_{report_object_id}.pdf"
            print(f"📄 PDF report also saved to: {pdf_filename}")
        else:
            pdf_web_path = None
            print(f"❌ Failed to generate PDF report: {pdf_filename}")

        db_record = {
            "_id": str(report_object_id),
            "testId": str(self.exercise_type.value),
            "userId": self.user_profile.user_id,
            "timestamp": datetime.now(),
            "score": int(overall_score),
            "videoPath": analyzed_video_url,
            "reportPath": pdf_web_path,
            "feedback": {
                "rule_based_summary": rule_based_analysis.get('summary', 'N/A'),
                "rule_based_key_findings": rule_based_analysis.get('key_findings', []),
                "rule_based_recommendations": rule_based_analysis.get('recommendations', []),
                "ai_summary": ai_analysis.get('summary', 'N/A'),
                "ai_key_findings": ai_analysis.get('key_findings', []),
                "ai_recommendations": ai_analysis.get('recommendations', []),
                "form_errors_breakdown": self.form_errors,
                "common_feedback": common_feedback,
                "full_feedback_history": self.all_feedback_per_frame,
            },
            "raw_report_data": report_json_data
        }
        print(db_record)

        if results_collection is not None:
            try:
                await results_collection.insert_one(db_record)
                print(f"✅ Report saved to MongoDB with _id: {report_object_id}")
            except Exception as e:
                print(f"❌ Error saving report to MongoDB: {e}")
        else:
            print("❌ MongoDB collection not initialized. Report not saved to DB.")

        return report_json_data, pdf_web_path


async def export_to_pdf(report_data: dict, filename: str) -> bool:
    try:
        if not _reportlab_available:
            print("ReportLab not available for PDF export")
            return False
            
        def _sync_export():
            doc = SimpleDocTemplate(filename, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
            styles = getSampleStyleSheet()
            story = []

            h2_style = ParagraphStyle(
                name='Heading2Custom',
                parent=styles['h2'],
                fontName='Helvetica-Bold',
                fontSize=14,
                leading=16,
                spaceAfter=6,
                textColor=colors.darkblue
            )
            styles.add(h2_style)

            title_style = ParagraphStyle(
                name='ReportTitle',
                parent=styles['Title'],
                fontName='Helvetica-Bold',
                fontSize=24,
                leading=28,
                spaceAfter=12,
                alignment=TA_CENTER,
                textColor=colors.black
            )
            story.append(Paragraph("Exercise Form Analysis Report", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # USER PROFILE SECTION
            user_profile = report_data.get('user_profile', {})
            story.append(Paragraph("<b>USER PROFILE</b>", h2_style))
            user_info = f"""
            <b>Name:</b> {user_profile.get('name', 'N/A')}<br/>
            <b>Age:</b> {user_profile.get('age', 'N/A')} years<br/>
            <b>Height:</b> {user_profile.get('height', 'N/A')} cm<br/>
            <b>Weight:</b> {user_profile.get('weight', 'N/A')} kg<br/>
            <b>BMI:</b> {user_profile.get('bmi', 0):.1f} ({user_profile.get('fitness_level', 'N/A')})<br/>
            """
            story.append(Paragraph(user_info, styles['Normal']))
            story.append(Spacer(1, 0.15*inch))
            
            # EXERCISE DETAILS SECTION
            exercise_details = report_data.get('exercise_details', {})
            story.append(Paragraph("<b>EXERCISE ANALYSIS</b>", h2_style))
            exercise_info = f"""
            <b>Exercise:</b> {exercise_details.get('type', 'N/A').replace('_', ' ').title()}<br/>
            <b>Date:</b> {exercise_details.get('date', 'N/A')[:19].replace('T', ' ')}<br/>
            <b>Duration:</b> {exercise_details.get('duration', 0):.2f} seconds<br/>
            <b>Reps Completed:</b> {report_data.get('performance', {}).get('rep_count', 'N/A')}<br/>
            """
            story.append(Paragraph(exercise_info, styles['Normal']))
            story.append(Spacer(1, 0.15*inch))
            
            # PERFORMANCE SCORE SECTION
            performance = report_data.get('performance', {})
            technical = report_data.get('technical_details', {})
            story.append(Paragraph("<b>PERFORMANCE SCORE</b>", h2_style))
            performance_info = f"""
            <b>Overall Score:</b> {performance.get('overall_score', 0):.1f}/100<br/>
            <b>Grade:</b> {performance.get('grade', 'N/A')}<br/>
            <b>Form Accuracy:</b> {performance.get('form_accuracy', 0):.1f}%<br/>
            <b>Total Frames Analyzed:</b> {technical.get('total_frames', 0)}<br/>
            <b>Correct Form Frames:</b> {technical.get('correct_frames', 0)}<br/>
            """
            story.append(Paragraph(performance_info, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # RULE-BASED ANALYSIS SECTION (SEPARATE)
            rule_based = report_data.get('rule_based_analysis', {})
            if rule_based:
                story.append(Paragraph("<b>RULE-BASED ANALYSIS</b>", h2_style))
                story.append(Paragraph("<b>Summary:</b>", styles['Heading3']))
                story.append(Paragraph(rule_based.get('summary', 'N/A'), styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                story.append(Paragraph("<b>Key Findings:</b>", styles['Heading3']))
                for finding in rule_based.get('key_findings', []):
                    story.append(Paragraph(f"• {finding}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                story.append(Paragraph("<b>Recommendations:</b>", styles['Heading3']))
                for rec in rule_based.get('recommendations', []):
                    story.append(Paragraph(f"• {rec}", styles['Normal']))
                story.append(Spacer(1, 0.2*inch))
            
            # AI ANALYSIS SECTION (SEPARATE)
            ai_analysis = report_data.get('ai_analysis', {})
            if ai_analysis:
                story.append(Paragraph("<b>AI-POWERED ANALYSIS</b>", h2_style))
                story.append(Paragraph("<b>AI Summary:</b>", styles['Heading3']))
                story.append(Paragraph(ai_analysis.get('summary', 'N/A'), styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                story.append(Paragraph("<b>AI Key Findings:</b>", styles['Heading3']))
                for finding in ai_analysis.get('key_findings', []):
                    story.append(Paragraph(f"• {finding}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                story.append(Paragraph("<b>AI Recommendations:</b>", styles['Heading3']))
                for rec in ai_analysis.get('recommendations', []):
                    story.append(Paragraph(f"• {rec}", styles['Normal']))
                story.append(Spacer(1, 0.2*inch))
            
            # METRICS SECTION
            story.append(Paragraph("<b>AVERAGE METRICS</b>", h2_style))
            metrics = report_data.get('metrics', {})
            if metrics:
                metrics_text = "<br/>".join([f"<b>{k.replace('_', ' ').title()}:</b> {v:.2f}" for k, v in metrics.items()])
                story.append(Paragraph(metrics_text, styles['Normal']))
            else:
                story.append(Paragraph("No metrics data available", styles['Normal']))
            
            story.append(Spacer(1, 0.2*inch))
            
            # FORM ERRORS BREAKDOWN
            story.append(Paragraph("<b>FORM ERRORS BREAKDOWN</b>", h2_style))
            form_errors = report_data.get('form_errors', {})
            if form_errors:
                error_text = "<br/>".join([f"<b>{k.replace('_', ' ').title()}:</b> {v} occurrences" for k, v in form_errors.items()])
                story.append(Paragraph(error_text, styles['Normal']))
            else:
                story.append(Paragraph("No form errors detected", styles['Normal']))

            doc.build(story)
            return True
        
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, _sync_export)
        return success
        
    except Exception as e:
        print(f"PDF export error: {e}")
        return False

async def create_workout_plan(user_profile: UserProfile, exercise_analysis: dict) -> dict:
    plan = {
        'user': user_profile.name,
        'fitness_level': user_profile.get_fitness_level(),
        'recommendations': []
    }
    
    if exercise_analysis['performance']['overall_score'] >= 80:
        plan['level'] = 'Advanced'
        plan['recommendations'] = [
            "Increase repetitions by 20%",
            "Add weighted variations",
            "Focus on explosive movements",
            "Incorporate plyometric exercises"
        ]
    elif exercise_analysis['performance']['overall_score'] >= 60:
        plan['level'] = 'Intermediate'
        plan['recommendations'] = [
            "Maintain current volume",
            "Focus on form perfection",
            "Add 2-3 more reps per set",
            "Include mobility work"
        ]
    else:
        plan['level'] = 'Beginner'
        plan['recommendations'] = [
            "Start with assisted variations",
            "Focus on partial range of motion",
            "Practice 3x per week",
            "Work on foundational strength"
        ]
    
    return plan