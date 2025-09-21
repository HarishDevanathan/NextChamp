# route.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import cv2
import numpy as np
import tempfile
import os
import shutil
from datetime import datetime
import json
from bson import ObjectId
from urllib.parse import unquote
import asyncio

from .utils import (
    ExerciseAnalyzer, 
    ExerciseType, 
    UserProfile, 
    init_database, 
    results_collection,
    create_workout_plan
)

# Initialize router
router = APIRouter(prefix="/test", tags=["Exercise Analysis"])

# Pydantic models for request/response
class AnalyzeTestRequest(BaseModel):
    user_id: str
    exercise_type: str  # Should be one of the ExerciseType enum names
    user_name: Optional[str] = ""
    age: Optional[int] = 0
    height: Optional[int] = 0  # cm
    weight: Optional[int] = 0  # kg

class AnalyzeTestResponse(BaseModel):
    success: bool
    message: str
    test_id: Optional[str] = None
    report_data: Optional[dict] = None
    pdf_path: Optional[str] = None
    overall_score: Optional[float] = None
    rep_count: Optional[int] = None
    form_accuracy: Optional[float] = None

class TestResultResponse(BaseModel):
    test_id: str
    user_id: str
    score: float
    timestamp: datetime
    exercise_type: str
    video_path: Optional[str] = None
    report_path: Optional[str] = None
    feedback: dict

# Initialize database connection on startup
@router.on_event("startup")
async def startup_event():
    await init_database()

def validate_exercise_type(exercise_type_str: str) -> ExerciseType:
    """Validate and convert exercise type string to enum"""
    exercise_type_map = {
        'VERTICAL_JUMP': ExerciseType.VERTICAL_JUMP,
        'SHUTTLE_RUN': ExerciseType.SHUTTLE_RUN,
        'SITUPS': ExerciseType.SITUPS,
        'PUSHUPS': ExerciseType.PUSHUPS,
        'PLANK_HOLD': ExerciseType.PLANK_HOLD,
        'STANDING_BROAD_JUMP': ExerciseType.STANDING_BROAD_JUMP,
        'SQUATS': ExerciseType.SQUATS,
        'ENDURANCE_RUN': ExerciseType.ENDURANCE_RUN,
        # Also accept lowercase
        'vertical_jump': ExerciseType.VERTICAL_JUMP,
        'shuttle_run': ExerciseType.SHUTTLE_RUN,
        'situps': ExerciseType.SITUPS,
        'pushups': ExerciseType.PUSHUPS,
        'plank_hold': ExerciseType.PLANK_HOLD,
        'standing_broad_jump': ExerciseType.STANDING_BROAD_JUMP,
        'squats': ExerciseType.SQUATS,
        'endurance_run': ExerciseType.ENDURANCE_RUN
    }
    
    if exercise_type_str not in exercise_type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid exercise type: {exercise_type_str}. Valid options: {list(exercise_type_map.keys())}"
        )
    
    return exercise_type_map[exercise_type_str]

async def process_video_analysis(
    video_file: UploadFile, 
    analyzer: ExerciseAnalyzer,
    temp_dir: str
) -> str:
    """Process video file and perform exercise analysis"""
    
    # Save uploaded video to temporary file
    video_path = os.path.join(temp_dir, f"input_{video_file.filename}")
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)
    
    # Open video for analysis
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not open video file")
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Setup output video writer
    output_path = os.path.join(temp_dir, f"analyzed_{video_file.filename}")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    frame_count = 0
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Process frame through analyzer
            analyzed_frame, feedback, metrics = analyzer.process_frame(frame)
            
            # Write analyzed frame to output video
            out.write(analyzed_frame)
            frame_count += 1
            
            # Optional: Limit processing for very long videos
            if frame_count > 3000:  # ~2 minutes at 30 FPS
                print("Video too long, stopping analysis")
                break
                
    except Exception as e:
        print(f"Error during video processing: {e}")
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")
    finally:
        cap.release()
        out.release()
    
    return output_path

@router.post("/analysetest", response_model=AnalyzeTestResponse)
async def analyze_test(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    user_id: str = Form(...),
    exercise_type: str = Form(...),
    user_name: str = Form(""),
    age: int = Form(0),
    height: int = Form(0),
    weight: int = Form(0)
):
    """
    Analyze exercise video and generate comprehensive report
    
    - **video**: Upload video file (MP4, AVI, MOV supported)
    - **user_id**: Unique user identifier
    - **exercise_type**: Type of exercise (SQUATS, PUSHUPS, etc.)
    - **user_name**: User's name (optional)
    - **age**: User's age in years (optional)
    - **height**: User's height in cm (optional)  
    - **weight**: User's weight in kg (optional)
    """
    
    # Validate inputs
    try:
        exercise_enum = validate_exercise_type(exercise_type)
    except HTTPException as e:
        return AnalyzeTestResponse(
            success=False,
            message=e.detail
        )
    
    # Validate video file
    if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        return AnalyzeTestResponse(
            success=False,
            message="Invalid video format. Please upload MP4, AVI, or MOV files."
        )
    
    # Create user profile
    user_profile = UserProfile(
        name=user_name,
        age=age,
        height=height,
        weight=weight,
        user_id=user_id
    )
    
    # Initialize analyzer
    analyzer = ExerciseAnalyzer(user_profile)
    analyzer.set_exercise_type(exercise_enum)
    
    # Create temporary directory for processing
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Process video
        print(f"🎬 Starting analysis for {exercise_type} exercise...")
        analyzed_video_path = await process_video_analysis(video, analyzer, temp_dir)
        
        # Generate comprehensive report
        print("📊 Generating comprehensive report...")
        report_data, pdf_path = await analyzer.generate_comprehensive_report(analyzed_video_path)
        
        # Move analyzed video to permanent location
        permanent_video_dir = "analyzed_videos"
        os.makedirs(permanent_video_dir, exist_ok=True)
        final_video_path = os.path.join(permanent_video_dir, f"analyzed_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video.filename}")
        shutil.move(analyzed_video_path, final_video_path)
        
        # Update report with final video path
        video_web_path = f"/{final_video_path}"
        print(video_web_path)
        print(pdf_path)
        # Schedule cleanup of temp directory
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        return AnalyzeTestResponse(
            success=True,
            message="Exercise analysis completed successfully",
            test_id=str(report_data.get('exercise_details', {}).get('date', str(ObjectId()))),
            report_data=report_data,
            pdf_path=pdf_path,
            overall_score=report_data['performance']['overall_score'],
            rep_count=report_data['performance']['rep_count'],
            form_accuracy=report_data['performance']['form_accuracy'],
            video_path=video_web_path
        )
        
    except Exception as e:
        # Cleanup on error
        cleanup_temp_dir(temp_dir)
        print(f"❌ Analysis failed: {str(e)}")
        return AnalyzeTestResponse(
            success=False,
            message=f"Analysis failed: {str(e)}"
        )

@router.get("/download/analyzed-video/{test_id}")
async def download_analyzed_video(test_id: str):
    """
    Download the analyzed video for a specific test.
    
    - **test_id**: Test identifier
    """
    
    if not results_collection:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        result = await results_collection.find_one({"testId": test_id})
        if not result:
            try:
                result = await results_collection.find_one({"_id": ObjectId(test_id)})
            except:
                pass
        
        if not result:
            raise HTTPException(status_code=404, detail="Test result not found")
        
        # Assuming the analyzed video path is stored in the 'raw_report_data' or directly in the document
        analyzed_video_server_path = result.get("raw_report_data", {}).get("analyzed_video_path")
        
        if not analyzed_video_server_path or not os.path.exists(analyzed_video_server_path):
            # Fallback if stored under a different key or not found
            # You might need to adjust this based on how you store the video path in the DB
            analyzed_video_server_path = result.get("videoPath") # Example fallback
            if not analyzed_video_server_path or not os.path.exists(analyzed_video_server_path):
                raise HTTPException(status_code=404, detail="Analyzed video file not found")
        
        # Extract filename for download
        filename = os.path.basename(analyzed_video_server_path)
        print(analyzed_video_server_path)
        return FileResponse(
            path=analyzed_video_server_path,
            filename=f"analyzed_video_{test_id}_{filename}",
            media_type='video/mp4' # Assuming MP4, adjust if other formats are used
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download analyzed video: {str(e)}")

@router.get("/results/{user_id}", response_model=List[TestResultResponse])
async def get_user_test_results(user_id: str, limit: int = 10):
    """
    Get test results for a specific user
    
    - **user_id**: User identifier
    - **limit**: Maximum number of results to return (default: 10)
    """
    
    if not results_collection:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        cursor = results_collection.find(
            {"userId": user_id}
        ).sort("timestamp", -1).limit(limit)
        
        results = []
        async for doc in cursor:
            result = TestResultResponse(
                test_id=doc.get("testId", str(doc.get("_id"))),
                user_id=doc.get("userId"),
                score=doc.get("score", 0.0),
                timestamp=doc.get("timestamp"),
                exercise_type=doc.get("raw_report_data", {}).get("exercise_details", {}).get("type", "UNKNOWN"),
                video_path=doc.get("videoPath"),
                report_path=doc.get("reportPath"),
                feedback=doc.get("feedback", {})
            )
            results.append(result)
        print(results)
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch results: {str(e)}")

@router.get("/result/{test_id}")
async def get_test_result_details(test_id: str):
    """
    Get detailed results for a specific test
    
    - **test_id**: Test identifier
    """
    
    if not results_collection:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Try to find by testId first, then by _id
        result = await results_collection.find_one({"testId": test_id})
        if not result:
            try:
                result = await results_collection.find_one({"_id": ObjectId(test_id)})
            except:
                pass
        
        if not result:
            raise HTTPException(status_code=404, detail="Test result not found")
        
        # Convert ObjectId to string for JSON serialization
        if '_id' in result:
            result['_id'] = str(result['_id'])
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch test result: {str(e)}")

@router.get("/workout-plan/{user_id}")
async def generate_workout_plan(user_id: str, test_id: Optional[str] = None):
    """
    Generate personalized workout plan based on user's latest or specific test result
    
    - **user_id**: User identifier
    - **test_id**: Specific test ID to base plan on (optional, uses latest if not provided)
    """
    
    if not results_collection:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Get test result
        if test_id:
            result = await results_collection.find_one({"testId": test_id, "userId": user_id})
        else:
            cursor = results_collection.find({"userId": user_id}).sort("timestamp", -1).limit(1)
            result = await cursor.to_list(length=1)
            result = result[0] if result else None
        
        if not result:
            raise HTTPException(status_code=404, detail="No test results found for user")
        
        # Extract user profile from result
        raw_data = result.get("raw_report_data", {})
        user_profile_data = raw_data.get("user_profile", {})
        
        user_profile = UserProfile(
            name=user_profile_data.get("name", ""),
            age=user_profile_data.get("age", 0),
            height=user_profile_data.get("height", 0),
            weight=user_profile_data.get("weight", 0),
            user_id=user_id
        )
        
        # Generate workout plan
        workout_plan = await create_workout_plan(user_profile, raw_data)
        
        return JSONResponse(content=workout_plan)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate workout plan: {str(e)}")

@router.get("/download/report/{test_id}")
async def download_report(test_id: str):
    """
    Download PDF report for a specific test
    """
    if not results_collection:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        test_id = unquote(test_id)  # decode URL-encoded timestamp

        # Try lookup by testId
        result = await results_collection.find_one({"testId": test_id})
        
        # Fallback: try as ObjectId if valid
        if not result:
            try:
                result = await results_collection.find_one({"_id": ObjectId(test_id)})
            except:
                pass

        if not result:
            raise HTTPException(status_code=404, detail=f"Test result not found for id {test_id}")

        report_path = result.get("reportPath")
        if not report_path:
            raise HTTPException(status_code=404, detail="Report path missing in DB")

        abs_path = os.path.abspath(report_path)
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail=f"Report file not found: {abs_path}")

        return FileResponse(
            path=abs_path,
            filename=f"exercise_report_{test_id}.pdf",
            media_type="application/pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")
@router.get("/stats/{user_id}")
async def get_user_stats(user_id: str):
    """
    Get user statistics and progress overview
    
    - **user_id**: User identifier
    """
    
    if not results_collection:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Aggregate user statistics
        pipeline = [
            {"$match": {"userId": user_id}},
            {"$group": {
                "_id": None,
                "total_tests": {"$sum": 1},
                "avg_score": {"$avg": "$score"},
                "max_score": {"$max": "$score"},
                "min_score": {"$min": "$score"},
                "latest_test": {"$max": "$timestamp"}
            }}
        ]
        
        cursor = results_collection.aggregate(pipeline)
        stats = await cursor.to_list(length=1)
        
        if not stats:
            return JSONResponse(content={
                "total_tests": 0,
                "avg_score": 0.0,
                "max_score": 0.0,
                "min_score": 0.0,
                "latest_test": None,
                "progress_trend": "No data available"
            })
        
        stat = stats[0]
        
        # Get recent scores for trend analysis
        recent_cursor = results_collection.find(
            {"userId": user_id}
        ).sort("timestamp", -1).limit(5)
        
        recent_scores = []
        async for doc in recent_cursor:
            recent_scores.append(doc.get("score", 0))
        
        # Simple trend analysis
        trend = "stable"
        if len(recent_scores) >= 3:
            if recent_scores[0] > recent_scores[-1]:
                trend = "improving"
            elif recent_scores[0] < recent_scores[-1]:
                trend = "declining"
        
        return JSONResponse(content={
            "total_tests": stat["total_tests"],
            "avg_score": round(stat["avg_score"], 2),
            "max_score": stat["max_score"],
            "min_score": stat["min_score"],
            "latest_test": stat["latest_test"],
            "progress_trend": trend,
            "recent_scores": recent_scores
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user stats: {str(e)}")

def cleanup_temp_dir(temp_dir: str):
    """Clean up temporary directory"""
    try:
        shutil.rmtree(temp_dir)
        print(f"🗑️ Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        print(f"⚠️ Failed to cleanup temp directory {temp_dir}: {e}")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_connected": results_collection is not None
    }