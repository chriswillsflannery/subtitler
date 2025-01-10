cd lambda-layers/ffmpeg

# download and extract ffmpeg
curl -O https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz
tar xf ffmpeg-git-amd64-static.tar.xz
mv ffmpeg-git-*/ffmpeg bin/
mv ffmpeg-git-*/ffprobe bin/

# clean  up
rm ffmpeg-git-amd64-static.tar.xz
rm -rf ffmpeg-git-*