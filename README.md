# Video Subtitler

An AWS-based system that automatically generates and adds subtitles to videos. When a video is uploaded to an S3 bucket, it triggers a Lambda function that extracts the audio, transcribes it using AWS Transcribe, and overlays the resulting subtitles on the video.

## Architecture

- **Upload S3 Bucket**: Stores uploaded videos and temporary audio files
- **Processed S3 Bucket**: Stores the final videos with subtitles
- **Lambda Function**: Processes videos using FFmpeg and AWS Transcribe
- **FFmpeg Layer**: Custom Lambda layer containing FFmpeg binaries

## Prerequisites

- Node.js and npm
- AWS CLI configured with appropriate credentials
- Docker Desktop (for local development and deployment)
- Python 3.9 or later

## Setup

1. Clone the repository:

```bash
git clone [repository-url]
cd video-subtitler
```

2. Install dependencies:

```bash
npm install
```

3. Set up the FFmpeg layer:

```bash
mkdir -p lambda-layers/ffmpeg/bin
chmod +x download-ffmpeg.sh
./download-ffmpeg.sh
```

4. Create a Python virtual environment for the Lambda function:

```bash
cd lambda
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

5. Deploy the stack:

```bash
cdk deploy
```

## Usage

1. Record a video on your mobile device
2. Upload the video to the upload S3 bucket using any S3-compatible app
3. The system will automatically:
   - Extract audio from the video
   - Transcribe the audio
   - Generate subtitles
   - Create a new video with embedded subtitles
4. Find the processed video in the processed S3 bucket

## Project Structure

```
video-subtitler/
├── bin/                    # CDK app entry point
├── lib/                    # CDK stack definition
├── lambda/                 # Lambda function code
│   ├── index.py           # Main Lambda handler
│   └── requirements.txt    # Python dependencies
├── lambda-layers/          # Lambda layers
│   └── ffmpeg/            # FFmpeg binaries
├── cdk.json               # CDK configuration
└── package.json           # Node.js dependencies
```

## Local Development

1. Ensure Docker Desktop is running
2. Use the Python virtual environment for Lambda function development
3. Test Lambda function locally using AWS SAM CLI (optional)

## Troubleshooting

- Ensure Docker is running before deploying
- Check CloudWatch Logs for Lambda function errors
- Verify S3 bucket permissions if upload/download fails
- Monitor AWS Transcribe job status in AWS Console
