import boto3
import os
import json
import subprocess
import uuid
import time

s3_client = boto3.client('s3')
transcribe_client = boto3.client('transcribe')

def handler(event, context):
    # get bucket and key from event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    print(f"Processing video: {key} from bucket: {bucket}")
    
    # create temporary files with unique names
    video_path = f"/tmp/{uuid.uuid4()}.mp4"
    audio_path = f"/tmp/{uuid.uuid4()}.wav"
    subtitle_path = f"/tmp/{uuid.uuid4()}.srt"
    output_path = f"/tmp/{uuid.uuid4()}.mp4"
    
    try:
        # download video file
        print(f"Downloading video to: {video_path}")
        s3_client.download_file(bucket, key, video_path)
        
        # verify video file size
        video_size = os.path.getsize(video_path)
        print(f"Downloaded video size: {video_size} bytes")
        if video_size == 0:
            raise ValueError("Downloaded video file is empty")
        
        # extract audio using ffmpeg with verbose output
        print("Extracting audio with FFmpeg")
        result = subprocess.run([
            'ffmpeg',  # Use ffmpg from PATH
            '-y',  # force overwrite output file
            '-i', video_path,
            '-vn',  # no video
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            audio_path
        ], capture_output=True, text=True)
        
        # print FFmpeg output for debugging
        print(f"FFmpeg stdout: {result.stdout}")
        print(f"FFmpeg stderr: {result.stderr}")
        
        # check FFmpeg was successful
        result.check_returncode()
        
        # verify audio file created and has content
        if not os.path.exists(audio_path):
            raise FileNotFoundError("Audio file was not created")
        
        audio_size = os.path.getsize(audio_path)
        print(f"Generated audio size: {audio_size} bytes")
        if audio_size == 0:
            raise ValueError("Generated audio file is empty")
            
        # upload audio to S3
        audio_key = f'audio/{os.path.basename(audio_path)}'
        print(f"Uploading audio to {bucket}/{audio_key}")
        s3_client.upload_file(audio_path, bucket, audio_key)
        
        # start transcription job
        job_name = f'transcribe-{context.aws_request_id}'
        print(f"Starting transcription job {job_name}")
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': f's3://{bucket}/{audio_key}'},
            MediaFormat='wav',
            LanguageCode='en-US',
            OutputBucketName=os.environ['PROCESSED_BUCKET_NAME']
        )
        
        # wait for transcription to complete
        print("Waiting for transcription to complete...")
        while True:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            print(f"Transcription job status: {job_status}")
            
            if job_status in ['COMPLETED', 'FAILED']:
                break
            if job_status == 'FAILED':
                raise Exception(f"Transcription failed: {status['TranscriptionJob'].get('FailureReason', 'Unknown reason')}")
            time.sleep(5)  # Wait 5 seconds before checking again
            
        # download and process transcript
        transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        print(f"Downloading transcript from: {transcript_uri}")
        
        # create SRT file from transcript
        response = requests.get(transcript_uri)
        transcript_data = response.json()
        
        with open(subtitle_path, 'w', encoding='utf-8') as srt_file:
            items = transcript_data['results']['items']
            current_subtitle = []
            subtitle_count = 1
            
            for item in items:
                if item.get('type') == 'pronunciation':
                    if not current_subtitle:
                        start_time = float(item['start_time'])
                        current_subtitle = [item]
                    elif float(item['start_time']) - float(current_subtitle[-1]['end_time']) > 1.0:
                        # Write current subtitle
                        end_time = float(current_subtitle[-1]['end_time'])
                        words = ' '.join(i['alternatives'][0]['content'] for i in current_subtitle)
                        
                        srt_file.write(f"{subtitle_count}\n")
                        srt_file.write(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n")
                        srt_file.write(f"{words}\n\n")
                        
                        subtitle_count += 1
                        start_time = float(item['start_time'])
                        current_subtitle = [item]
                    else:
                        current_subtitle.append(item)
        
        # Add subtitles to video using ffmpeg
        print("Adding subtitles to video")
        result = subprocess.run([
            '/opt/ffmpeg/ffmpeg',
            '-y',
            '-i', video_path,
            '-vf', f'subtitles={subtitle_path}',
            '-c:a', 'copy',
            output_path
        ], capture_output=True, text=True)
        
        print(f"FFmpeg stdout: {result.stdout}")
        print(f"FFmpeg stderr: {result.stderr}")
        result.check_returncode()
        
        # upload processed video
        output_key = f'processed/{os.path.basename(key)}'
        print(f"Uploading processed video to: {output_key}")
        s3_client.upload_file(
            output_path,
            os.environ['PROCESSED_BUCKET_NAME'],
            output_key
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Video processing completed',
                'processedVideo': output_key
            })
        }
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        raise
        
    finally:
        print("Cleaning up temporary files")
        for path in [video_path, audio_path, subtitle_path, output_path]:
            if os.path.exists(path):
                os.remove(path)

def format_timestamp(seconds):
    """Convert seconds to SRT timestamp format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"