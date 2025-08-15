import os
import ffmpeg

def get_video_attributes(file_path):
    """
    वीडियो की चौड़ाई, ऊंचाई, और अवधि (duration) return करता है।
    """
    try:
        probe = ffmpeg.probe(file_path)
        video_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'video']
        if not video_streams:
            return None
        video = video_streams[0]
        width = video.get('width')
        height = video.get('height')
        duration = float(video.get('duration', 0))
        return {"width": width, "height": height, "duration": duration}
    except Exception as e:
        print(f"Error getting video attributes: {e}")
        return None


def get_video_thumb(file_path, output_thumb_path="thumb.jpg", time_pos=1):
    """
    वीडियो से thumbnail निकालकर save करता है।
    """
    try:
        (
            ffmpeg
            .input(file_path, ss=time_pos)
            .filter('scale', 320, -1)
            .output(output_thumb_path, vframes=1)
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_thumb_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None