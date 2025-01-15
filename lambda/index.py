import boto3
import os
import json
import subprocess
import tempfile
import uuid

s3_client = boto3.client('s3')
transcribe_client = boto3.client('transcribe')

def handler(event, context):
  # get bucket and key from event
  bucket = event['Records'][0]['s3']['bucket']['name']
  key = event['Records'][0]['s3']['object']['key']

  # download video file
  with tempfile.NamedTemporaryFile(suffix='.mp4') as video_file:
    print(f"Downloading  {key} from {bucket}")
    s3_client.download_file(bucket, key, video_file.name)

    #extract audio with ffmpeg
    audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    try:
      print(f"Extracting audio to {audio_file.name}")
      subprocess.run([
        'ffmpeg', '-i', video_file.name,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        audio_file.name
      ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
      print(f"FFmpeg error: {e.stderr.decode()}")
      raise

    #upload audio wav to s3 for transcription
    audio_key = f'audio/{uuid.uuid4()}.wav'
    print(f"Uploading audio to {audio_key}")
    s3_client.upload_file(audio_file.name, bucket, audio_key)

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

    #wait for transcription to complete
    while True:
      status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
      if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
        break
    if status['TranscriptionJob']['TranscriptionJobStatus'] == 'FAILED':
      raise Exception('Transcription failed')
    
    # download transcript
    transcript_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
    s3_client.download_file(
      os.environ['PROCESSED_BUCKET_NAME'],
      f'{job_name}.json',
      transcript_file.name
    )

    # convert to SRT format so we can retain timestamps
    with open(transcript_file.name, 'r') as f:
      transcript_data = json.load(f)
    items = transcript_data['results']['items']
    current_subtitle = []
    subtitles = []

    for item in items:
      if 'start_time' in item:
        if not current_subtitle:
          current_subtitle = [item]
        elif float(item['start_time']) - float(current_subtitle[-1]['end_time']) > 1.0:
          subtitles.append(current_subtitle)
          current_subtitle = [item]
        else:
          current_subtitle.append(item)
    
    srt_file = tempfile.NamedTemporaryFile(suffix='.srt', delete=False)
    with open(srt_file.name, 'w') as f:
      for i, subtitle in enumerate(subtitles, 1):
        start_time = subtitle[0]['start_time']
        end_time = subtitle[-1]['end_time']
        text = ' '.join(item['alternatives'][0]['content'] for item in subtitle)

        f.write(f'{i}\n')
        f.write(f'{format_timestamp(float(start_time))} --> {format_timestamp(float(end_time))}\n')
        f.write(f'{text}\n\n')

    #add subtitles to vieo with ffmpeg
    output_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    subprocess.run([
      'ffmpeg', '-i', video_file.name,
      '-vf', f'subtitles={srt_file.name}',
      '-c:a', 'copy',
      output_file.name
    ])

    #upload processed video
    processed_key = f'processed/{os.path.basename(key)}'
    s3_client.upload_file(
      output_file.name,
      os.environ['PROCESSED_BUCKET_NAME'],
      processed_key
    )

    #clean up temp files
    os.unlink(audio_file.name)
    os.unlink(transcript_file.name)
    os.unlink(srt_file.name)
    os.unlink(output_file.name)

    return {
      'statusCode': 200,
      'body': json.dumps({
        'message': 'Video processing completed',
        'processed video key': processed_key
      })
    }
  
  def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'