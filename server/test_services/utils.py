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
        self.previous_state = "up"
        self.rep_phase = "waiting"
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
            'body_alignment': 0
        }
        self.rep_quality_scores = []
        self.all_feedback_per_frame = []

    def detect_squat_phase(self, knee_angle, hip_height):
        current_phase = self.rep_phase

        TOP_KNEE_ANGLE = 160
        BOTTOM_KNEE_ANGLE = 100

        if knee_angle > TOP_KNEE_ANGLE:
            if current_phase == "going_up":
                self.rep_count += 1
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

    def detect_pushup_phase(self, elbow_angle, shoulder_height):
        current_phase = self.rep_phase

        TOP_ELBOW_ANGLE = 160
        BOTTOM_ELBOW_ANGLE = 90

        if elbow_angle > TOP_ELBOW_ANGLE:
            if current_phase == "going_up":
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

    def calculate_rep_quality(self):
        if len(self.metrics_history) < 10:
            return 50

        recent_metrics = self.metrics_history[-10:]
        recent_feedback = self.feedback_history[-10:]

        good_frames = sum(1 for fb in recent_feedback if any(positive in fb.lower() for positive in ["good", "excellent", "perfect", "great", "nice", "complete"]))
        quality_score = (good_frames / len(recent_feedback)) * 100

        return quality_score

    def set_exercise_type(self, exercise_type: ExerciseType):
        self.exercise_type = exercise_type
        self._load_reference_metrics()
        self.start_time = time.time()
        self.rep_phase = "at_top"

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

    def calculate_angle(self, a, b, c):
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)

        ba = a - b
        bc = c - b

        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))

        return np.degrees(angle)

    def analyze_squats(self, landmarks, h, w):
        feedback = []
        is_correct = True

        hip = np.array([landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * w,
                       landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * h])
        knee = np.array([landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * w,
                        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * h])
        ankle = np.array([landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * w,
                         landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * h])
        shoulder = np.array([landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * w,
                            landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * h])

        knee_angle = self.calculate_angle(hip, knee, ankle)
        torso_angle = self.calculate_angle(shoulder, hip, knee)
        hip_height = hip[1]

        new_phase = self.detect_squat_phase(knee_angle, hip_height)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        if self.rep_phase in ["going_down", "at_bottom"]:
            if knee_angle < self.reference_metrics['knee_angle_range'][0]:
                feedback.append("Going too deep! Control the descent.")
                self.form_errors['depth_issues'] += 1
                is_correct = False
            elif knee_angle > 130 and self.rep_phase == "at_bottom":
                feedback.append("Go deeper! Aim for 90 degrees.")
                self.form_errors['depth_issues'] += 1
                is_correct = False

            if torso_angle < self.reference_metrics['torso_angle_range'][0]:
                feedback.append("Chest up! Don't lean forward too much.")
                self.form_errors['torso_lean'] += 1
                is_correct = False

        alignment_score = self._check_alignment(hip, knee, ankle)
        if alignment_score < self.reference_metrics['hip_knee_ankle_alignment'] and self.rep_phase != "at_top":
            feedback.append("Keep knees aligned with toes.")
            self.form_errors['knee_alignment'] += 1
            is_correct = False

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
        feedback = []
        is_correct = True

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

        elbow_angle = self.calculate_angle(shoulder, elbow, wrist)
        shoulder_height = shoulder[1]

        new_phase = self.detect_pushup_phase(elbow_angle, shoulder_height)
        phase_changed = new_phase != self.rep_phase
        self.rep_phase = new_phase

        if self.rep_phase in ["going_down", "at_bottom"]:
            if elbow_angle < self.reference_metrics['elbow_angle_range'][0]:
                feedback.append("Great depth! Now push up!")
            elif elbow_angle > 130 and self.rep_phase == "at_bottom":
                feedback.append("Go lower! Get closer to the ground.")
                self.form_errors['depth_issues'] += 1
                is_correct = False

        alignment_score = self._check_alignment(shoulder, hip, ankle)
        if alignment_score < self.reference_metrics['shoulder_hip_ankle_alignment'] and self.rep_phase != "at_top":
            feedback.append("Keep your body straight! Engage your core.")
            self.form_errors['body_alignment'] += 1
            is_correct = False

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

    def _check_alignment(self, a, b, c):
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
        if not self.metrics_history:
            return 50

        correct_frames = sum(1 for fb in self.feedback_history if any(positive in fb.lower() for positive in ["good", "excellent", "perfect", "great", "nice"]))
        total_frames = len(self.feedback_history)
        form_accuracy = (correct_frames / total_frames) if total_frames > 0 else 0

        rep_quality_avg = sum(self.rep_quality_scores) / len(self.rep_quality_scores) if self.rep_quality_scores else 50

        total_deviation = 0
        deviation_count = 0

        for metrics in self.metrics_history:
            if metrics:
                for key, value in metrics.items():
                    if 'deviation' in key and value > 0:
                        total_deviation += min(value, 45)
                        deviation_count += 1

        avg_deviation = total_deviation / deviation_count if deviation_count > 0 else 0
        deviation_score = max(0, 1 - (avg_deviation / 45))

        base_score = 60
        form_bonus = form_accuracy * 25
        rep_bonus = (rep_quality_avg / 100) * 10
        precision_bonus = deviation_score * 5

        overall_score = base_score + form_bonus + rep_bonus + precision_bonus

        if self.rep_count > 0:
            rep_bonus_points = min(self.rep_count * 2, 10)
            overall_score += rep_bonus_points

        return min(100, max(30, overall_score))

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

    def process_frame(self, image):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)

        h, w, _ = image.shape
        feedback_list = []
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
            elif self.exercise_type == ExerciseType.PUSHUPS:
                self.is_correct_form, feedback_list, metrics = self.analyze_pushups(landmarks, h, w)
            else:
                feedback_list.append(f"Analysis for {self.exercise_type.name.replace('_', ' ').title()} not yet implemented.")

            if not feedback_list:
                feedback_list.append("Good form!")

            feedback_text = " | ".join(feedback_list)

            self.feedback_history.append(feedback_text)
            self.metrics_history.append(metrics)
            self.all_feedback_per_frame.append(feedback_list)

            y_offset = 30
            for key, value in metrics.items():
                if not 'deviation' in key and key != 'phase':
                    if isinstance(value, (int, float)):
                        cv2.putText(image, f"{key}: {value:.1f}", (10, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    else:
                        cv2.putText(image, f"{key}: {value}", (10, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    y_offset += 25

            phase_color = (255, 255, 0) if self.rep_phase in ["going_down", "going_up"] else (0, 255, 255)
            cv2.putText(image, f"Phase: {self.rep_phase.replace('_', ' ').title()}", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, phase_color, 2)
            y_offset += 25

            color = (0, 255, 0) if self.is_correct_form else (0, 0, 255)
            cv2.putText(image, feedback_text, (10, h - 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.putText(image, f"Reps: {self.rep_count}", (w - 150, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)

            current_score = self.calculate_overall_score()
            cv2.putText(image, f"Score: {current_score:.0f}/100", (w - 200, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        return image, feedback_text, metrics

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