import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3notifications from 'aws-cdk-lib/aws-s3-notifications';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class SubtitlerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const uploadBucket = new s3.Bucket(this, 'VideoUploadBucket', {
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      cors: [{
        allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET],
        allowedOrigins: ['*'],
        allowedHeaders: ['*'],
      }]
    });
    const processedBucket = new s3.Bucket(this, 'ProcessedVideosBucket', {
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // custom ffmpeg layer
    const ffmpegLayer = new lambda.LayerVersion(this, 'FFmpegLayer', {
      code: lambda.Code.fromAsset('lambda-layers/ffmpeg'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
      description: 'FFmpeg binaries'
    });

    // create lambda function for video processing
    const processingFunction = new lambda.Function(this, 'VideoProcessingFunction', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_9.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
        },
      }),
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      layers: [ffmpegLayer],
      environment: {
        PROCESSED_BUCKET_NAME: processedBucket.bucketName
      }
    });

    // give lambda read/write permissions
    uploadBucket.grantRead(processingFunction);
    processedBucket.grantWrite(processingFunction);

    // give transcribe permissions to lambda role
    processingFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['transcribe:StartTranscriptionJob', 'transcribe:GetTranscriptionJob'],
      resources: ['*']
    }));

    // add s3 notif trigger to lambda
    uploadBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3notifications.LambdaDestination(processingFunction)
    );
  }
}
