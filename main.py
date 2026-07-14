import os
import re
import uuid
import threading
import time
import ssl
import shutil
import stat

try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
except ImportError:
    pass

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.image import AsyncImage
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import platform
from kivy.metrics import dp, sp

if platform != 'android':
    Window.size = (410, 730)
Window.clearcolor = (0.06, 0.06, 0.08, 1)

PRIMARY_COLOR = (0.95, 0.33, 0.33, 1)
SECONDARY_COLOR = (0.12, 0.12, 0.16, 1)
BG_DARK = (0.06, 0.06, 0.08, 1)
TEXT_WHITE = (1, 1, 1, 1)
TEXT_MUTED = (0.55, 0.55, 0.6, 1)
SUCCESS_GREEN = (0.15, 0.68, 0.37, 1)
INPUT_BG = (0.14, 0.14, 0.18, 1)

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


def get_ffmpeg_location():
    """Extracts the bundled ffmpeg binary into the app's private storage on Android
    and also produces an 'ffprobe' copy, since yt-dlp's audio postprocessor needs
    both binaries and Android apps normally ship only a single static executable."""
    if platform != 'android':
        return None

    app = App.get_running_app()
    if not app:
        return None

    internal_dir = app.user_data_dir
    src_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg.bin')
    target_ffmpeg = os.path.join(internal_dir, 'ffmpeg')
    target_ffprobe = os.path.join(internal_dir, 'ffprobe')

    if os.path.exists(src_ffmpeg):
        for target in (target_ffmpeg, target_ffprobe):
            if not os.path.exists(target) or os.path.getsize(src_ffmpeg) != os.path.getsize(target):
                try:
                    shutil.copy(src_ffmpeg, target)
                    os.chmod(target, 0o755)
                except Exception as e:
                    print(f"Error extracting ffmpeg binary: {e}")

    if os.path.exists(target_ffmpeg) and os.path.exists(target_ffprobe):
        return internal_dir
    return None


class FluentCard(BoxLayout):
    def __init__(self, bg_color=SECONDARY_COLOR, radius=[dp(14)], **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class RoundedButton(Button):
    def __init__(self, bg_color=PRIMARY_COLOR, radius=[dp(12)], **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.radius = radius

        with self.canvas.before:
            self.color_instruction = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_state(self, instance, value):
        if value == 'down':
            self.color_instruction.rgba = (self.bg_color[0]*0.8, self.bg_color[1]*0.8, self.bg_color[2]*0.8, self.bg_color[3])
        else:
            self.color_instruction.rgba = self.bg_color


class RoundedTextInput(TextInput):
    """Text input with a fully custom rounded-rectangle background drawn on the
    canvas, matching the rest of the app's card styling (instead of the default
    square Kivy TextInput background)."""
    def __init__(self, **kwargs):
        # لا نرسم أي خلفية داخل الـ TextInput نفسه، لأن هذا الويدجت يعيد رسم
        # canvas.before الخاص به تلقائياً عند كل تحديث للنص، وهذا كان يمسح أي
        # رسم يدوي نضيفه هنا (وهو سبب اختفاء الصندوق والنص المكتوب بالكامل).
        # الحل: نجعله شفافاً تماماً، ونضعه داخل بطاقة FluentCard منفصلة تتولى
        # رسم الخلفية الدائرية بدلاً منه (انظر build_ui).
        kwargs['background_normal'] = ''
        kwargs['background_active'] = ''
        kwargs['background_disabled_normal'] = ''
        super().__init__(**kwargs)

        self.background_color = (0, 0, 0, 0)
        self.foreground_color = (1, 1, 1, 1)
        self.hint_text_color = (0.55, 0.55, 0.6, 1)
        self.cursor_color = (0.95, 0.33, 0.33, 1)
        self.selection_color = (0.95, 0.33, 0.33, 0.35)
        self.padding = [dp(14), dp(12), dp(14), dp(12)]


class CustomSpinnerOption(SpinnerOption):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0.15, 0.15, 0.20, 1)
        self.color = (1, 1, 1, 1)
        self.font_size = sp(13)


class RoundedSpinner(Spinner):
    def __init__(self, bg_color=(0.18, 0.18, 0.24, 1), radius=[dp(10)], **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.option_cls = CustomSpinnerOption
        self.bg_color = bg_color
        self.radius = radius

        with self.canvas.before:
            self.color_instruction = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class DownloadJob:
    def __init__(self, url, title, thumbnail, duration, uploader, formats, selected_format_id, format_type='video'):
        self.id = uuid.uuid4().hex[:10]
        self.url = url
        self.title = title
        self.thumbnail = thumbnail
        self.duration = duration
        self.uploader = uploader
        self.formats = formats
        self.selected_format_id = selected_format_id
        self.format_type = format_type
        self.status = 'ready'
        self.progress = 0.0
        self.error = None
        self.file_path = None
        self.filename = None
        self.speed = "0 KB/s"
        self.eta = "--:--"
        self.ydl_opts = {}
        self.is_cancelled = False


class DownloadManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.jobs = []
            cls._instance.job_map = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def add_job(self, job):
        with self._lock:
            self.jobs.append(job)
            self.job_map[job.id] = job
        return job.id

    def get_job(self, job_id):
        return self.job_map.get(job_id)

    def remove_job(self, job_id):
        with self._lock:
            job = self.job_map.pop(job_id, None)
            if job:
                if job.status == 'downloading':
                    job.is_cancelled = True
                if job in self.jobs:
                    self.jobs.remove(job)

    def _get_private_download_dir(self):
        """كل الملفات تُنزَّل أولاً إلى مجلد خاص بالتطبيق (لا يحتاج أي إذن على أندرويد
        الحديث)، ثم تُنشر لاحقاً إلى مجلد التنزيلات العام الظاهر لبقية التطبيقات."""
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                ext_dir = activity.getExternalFilesDir(None)
                if ext_dir:
                    download_dir = os.path.join(ext_dir.getAbsolutePath(), "DownKaze")
                else:
                    download_dir = os.path.join(activity.getFilesDir().getAbsolutePath(), "DownKaze")
            except Exception:
                download_dir = "."
        else:
            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir)
            except Exception:
                download_dir = "."
        return download_dir

    def start_download(self, job_id):
        job = self.get_job(job_id)
        if not job or job.status in ('downloading', 'done'):
            return False

        job.status = 'downloading'
        job.progress = 0.0
        job.is_cancelled = False

        download_dir = self._get_private_download_dir()

        opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'cachedir': False,
        }

        ffmpeg_dir = get_ffmpeg_location()
        if ffmpeg_dir:
            opts['ffmpeg_location'] = ffmpeg_dir

        if job.format_type == 'audio':
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            # الصيغ المعروضة كلها صيغ مدمجة (صوت+صورة) أصلاً، لا حاجة لأي دمج بعد التحميل
            opts['format'] = job.selected_format_id

        def progress_hook(d):
            if job.is_cancelled:
                raise Exception("Cancelled")
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    job.progress = (downloaded / total) * 100
                job.speed = d.get('_speed_str', '0 KB/s')
                job.eta = d.get('_eta_str', '--:--')
            elif d['status'] == 'finished':
                job.progress = 100.0
                job.file_path = d.get('filename')
                job.filename = os.path.basename(job.file_path) if job.file_path else None

        def postprocessor_hook(d):
            # يلتقط اسم الملف النهائي الصحيح بعد تحويل الصوت إلى mp3
            if d.get('status') == 'finished':
                info = d.get('info_dict', {}) or {}
                final_path = info.get('filepath') or info.get('filename')
                if final_path:
                    job.file_path = final_path
                    job.filename = os.path.basename(final_path)

        opts['progress_hooks'] = [progress_hook]
        opts['postprocessor_hooks'] = [postprocessor_hook]
        job.ydl_opts = opts

        t = threading.Thread(target=self._run_ydl, args=(job,))
        t.daemon = True
        t.start()
        return True

    def _run_ydl(self, job):
        try:
            with yt_dlp.YoutubeDL(job.ydl_opts) as ydl:
                ydl.download([job.url])

            if job.is_cancelled:
                return

            if platform == 'android' and job.file_path and os.path.exists(job.file_path):
                try:
                    mime = 'audio/mpeg' if job.format_type == 'audio' else 'video/mp4'
                    self._publish_to_public_downloads_android(job.file_path, job.filename, mime)
                    job.status = 'done'
                except Exception as pub_err:
                    job.status = 'error'
                    job.error = f"تم التحميل لكن فشل نقله لمجلد التنزيلات العام: {pub_err}"
            else:
                job.status = 'done'
        except Exception as e:
            if job.is_cancelled:
                job.status = 'ready'
                job.progress = 0.0
            else:
                job.status = 'error'
                job.error = str(e)

    def _publish_to_public_downloads_android(self, temp_path, filename, mime_type):
        """ينشر الملف من المجلد الخاص بالتطبيق إلى مجلد Downloads العام باستخدام
        مكتبة androidstorage4kivy، وهي المكتبة الموصى بها رسمياً من فريق Kivy
        لهذا الغرض بالذات (بدل التعامل اليدوي مع ContentResolver/ContentValues
        عبر pyjnius، والذي كان يفشل بسبب صعوبة مطابقة أنواع الدوال Java تلقائياً)."""
        try:
            from androidstorage4kivy import SharedStorage
        except ImportError:
            raise Exception(
                "مكتبة androidstorage4kivy غير مثبتة. أضف 'androidstorage4kivy' "
                "إلى requirements في buildozer.spec وأعد بناء الـ APK."
            )

        shared_storage = SharedStorage()
        shared_uri = shared_storage.copy_to_shared(temp_path)
        if not shared_uri:
            raise Exception("فشل نسخ الملف إلى مجلد Downloads العام")

        try:
            os.remove(temp_path)
        except Exception:
            pass

    def cancel_download(self, job_id):
        job = self.get_job(job_id)
        if job:
            job.is_cancelled = True
            job.status = 'ready'
            job.progress = 0.0
            return True
        return False


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.format_type = 'video'
        self.current_jobs_data = []
        self.build_ui()

    def build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(14))

        header = Label(
            text='[b][color=#f25454]Down[/color][color=#ffffff]Kaze[/color][/b]',
            markup=True, font_size=sp(28), size_hint_y=None, height=dp(50), halign='center'
        )
        root.add_widget(header)

        input_card = FluentCard(
            bg_color=INPUT_BG, radius=[dp(16)],
            size_hint_y=None, height=dp(95), padding=dp(2)
        )
        self.url_input = RoundedTextInput(
            hint_text='Paste video links here... (one per line)',
            multiline=True, font_size=sp(14)
        )
        input_card.add_widget(self.url_input)
        root.add_widget(input_card)

        selector_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(8))
        self.video_toggle = RoundedButton(
            text='Video MP4', bg_color=PRIMARY_COLOR,
            color=TEXT_WHITE, font_size=sp(13), bold=True
        )
        self.video_toggle.bind(on_press=lambda x: self.switch_mode('video'))

        self.audio_toggle = RoundedButton(
            text='Audio MP3', bg_color=(0.11, 0.11, 0.14, 1),
            color=TEXT_MUTED, font_size=sp(13), bold=True
        )
        self.audio_toggle.bind(on_press=lambda x: self.switch_mode('audio'))

        selector_layout.add_widget(self.video_toggle)
        selector_layout.add_widget(self.audio_toggle)
        root.add_widget(selector_layout)

        fetch_btn = RoundedButton(
            text='Analyze Link(s)', bg_color=PRIMARY_COLOR,
            color=TEXT_WHITE, font_size=sp(15), bold=True, size_hint_y=None, height=dp(46)
        )
        fetch_btn.bind(on_press=self.fetch_links)
        root.add_widget(fetch_btn)

        scroll = ScrollView(bar_width=dp(4))
        self.cards_container = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        self.cards_container.bind(minimum_height=self.cards_container.setter('height'))
        scroll.add_widget(self.cards_container)
        root.add_widget(scroll)

        footer = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(45))
        self.dashboard_btn = RoundedButton(
            text='Active Downloads Dashboard', bg_color=(0.15, 0.15, 0.20, 1),
            color=TEXT_WHITE, font_size=sp(13)
        )
        self.dashboard_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'downloads'))
        footer.add_widget(self.dashboard_btn)
        root.add_widget(footer)

        self.add_widget(root)

    def switch_mode(self, mode):
        self.format_type = mode
        if mode == 'video':
            self.video_toggle.bg_color = PRIMARY_COLOR
            self.video_toggle.color = TEXT_WHITE
            self.audio_toggle.bg_color = (0.11, 0.11, 0.14, 1)
            self.audio_toggle.color = TEXT_MUTED
        else:
            self.audio_toggle.bg_color = PRIMARY_COLOR
            self.audio_toggle.color = TEXT_WHITE
            self.video_toggle.bg_color = (0.11, 0.11, 0.14, 1)
            self.video_toggle.color = TEXT_MUTED

        self.video_toggle.canvas.before.children[0].rgba = self.video_toggle.bg_color
        self.audio_toggle.canvas.before.children[0].rgba = self.audio_toggle.bg_color

    def fetch_links(self, instance):
        if yt_dlp is None:
            self.show_popup("Error", "yt-dlp is missing.")
            return

        links = re.findall(r'https?://\S+', self.url_input.text)
        if not links:
            self.show_popup("Error", "Please enter a valid video link.")
            return

        self.cards_container.clear_widgets()
        self.current_jobs_data = []

        for index, url in enumerate(links[:5]):
            loading_card = FluentCard(orientation='vertical', size_hint_y=None, height=dp(80), padding=dp(16))
            loading_card.add_widget(Label(text="Extracting metadata & qualities...", color=TEXT_MUTED, font_size=sp(13)))
            self.cards_container.add_widget(loading_card)

            self.current_jobs_data.append({'url': url, 'card': loading_card, 'metadata': None})
            threading.Thread(target=self._async_extract, args=(url, index)).start()

    def _async_extract(self, url, index):
        try:
            ydl_opts = {
                'nocheckcertificate': True,
                'quiet': True,
                'cachedir': False,
                'no_warnings': True,
                'extract_flat': False
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                meta = ydl.extract_info(url, download=False)

            # الاحتفاظ فقط بالصيغ المدمجة (Progressive) التي تحتوي على صوت وصورة معاً
            unique_formats = {}
            for f in meta.get('formats', []):
                h = f.get('height')
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')
                has_video = bool(vcodec) and vcodec != 'none'
                has_audio = bool(acodec) and acodec != 'none'
                if h and has_video and has_audio:
                    label = f"{h}p"
                    if h not in unique_formats:
                        unique_formats[h] = {
                            'id': f['format_id'], 'label': label, 'height': h
                        }

            formats = list(unique_formats.values())
            formats.sort(key=lambda x: x['height'], reverse=True)

            data = {
                'title': meta.get('title', 'Untitled Media'),
                'thumbnail': meta.get('thumbnail', ''),
                'duration': meta.get('duration', 0),
                'uploader': meta.get('uploader', 'Unknown Creator'),
                'formats': formats,
                'selected_format_id': formats[0]['id'] if formats else None,
                'url': url
            }
            Clock.schedule_once(lambda dt: self._build_media_card(index, data), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self._build_error_card(index, str(e)), 0)

    def _build_media_card(self, index, data):
        if index >= len(self.current_jobs_data): return

        card = FluentCard(orientation='vertical', size_hint_y=None, height=dp(155), padding=dp(12), spacing=dp(8))

        top_row = BoxLayout(orientation='horizontal', spacing=dp(12), size_hint_y=None, height=dp(60))
        thumb = AsyncImage(source=data['thumbnail'], size_hint_x=0.3, allow_stretch=True, keep_ratio=False)
        top_row.add_widget(thumb)

        text_info = BoxLayout(orientation='vertical', spacing=dp(2))
        title_lbl = Label(text=data['title'][:40] + '...', font_size=sp(13), bold=True, halign='left', size_hint_y=None, height=dp(18))
        title_lbl.bind(size=title_lbl.setter('text_size'))
        author_lbl = Label(text=f"{data['uploader']} • {int(data['duration']//60)}m", font_size=sp(11), color=TEXT_MUTED, halign='left')
        author_lbl.bind(size=author_lbl.setter('text_size'))

        text_info.add_widget(title_lbl)
        text_info.add_widget(author_lbl)
        top_row.add_widget(text_info)
        card.add_widget(top_row)

        actions = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(38))

        if self.format_type == 'video' and data['formats']:
            quality_labels = [f['label'] for f in data['formats']]
            quality_spinner = RoundedSpinner(
                text=quality_labels[0], values=quality_labels, size_hint_x=0.45,
                color=TEXT_WHITE, font_size=sp(12), bold=True
            )
            card.quality_spinner = quality_spinner
            actions.add_widget(quality_spinner)
        elif self.format_type == 'video' and not data['formats']:
            actions.add_widget(Label(text="No combined quality found", color=TEXT_MUTED, font_size=sp(11), size_hint_x=0.45))
            card.quality_spinner = None
        else:
            actions.add_widget(Label(text="Format: MP3 Audio", color=TEXT_WHITE, font_size=sp(12), size_hint_x=0.45))
            card.quality_spinner = None

        dl_btn = RoundedButton(text='Download Now', bg_color=PRIMARY_COLOR, color=TEXT_WHITE, bold=True, size_hint_x=0.55)
        dl_btn.bind(on_press=lambda x: self.trigger_download(data, card))
        actions.add_widget(dl_btn)
        card.add_widget(actions)

        old_card = self.current_jobs_data[index]['card']
        if old_card in self.cards_container.children:
            pos_idx = self.cards_container.children.index(old_card)
            self.cards_container.remove_widget(old_card)
            self.cards_container.add_widget(card, index=pos_idx)
        else:
            self.cards_container.add_widget(card)

        self.current_jobs_data[index]['card'] = card

    def _build_error_card(self, index, error_msg):
        if index >= len(self.current_jobs_data): return
        card = FluentCard(bg_color=(0.25, 0.08, 0.08, 1), size_hint_y=None, height=dp(75), padding=dp(12))
        card.add_widget(Label(text=f"Error: {error_msg[:60]}...", color=TEXT_WHITE, font_size=sp(12), halign='center'))

        old_card = self.current_jobs_data[index]['card']
        if old_card in self.cards_container.children:
            pos_idx = self.cards_container.children.index(old_card)
            self.cards_container.remove_widget(old_card)
            self.cards_container.add_widget(card, index=pos_idx)
        else:
            self.cards_container.add_widget(card)

        self.current_jobs_data[index]['card'] = card

    def trigger_download(self, data, card):
        if self.format_type == 'video' and not data.get('selected_format_id'):
            self.show_popup("Error", "No combined audio+video quality is available for this link.")
            return

        selected_format_id = data['selected_format_id']

        if hasattr(card, 'quality_spinner') and card.quality_spinner:
            chosen_label = card.quality_spinner.text
            for f in data['formats']:
                if f['label'] == chosen_label:
                    selected_format_id = f['id']
                    break

        dm = DownloadManager()
        job = DownloadJob(
            url=data['url'], title=data['title'], thumbnail=data['thumbnail'],
            duration=data['duration'], uploader=data['uploader'], formats=data['formats'],
            selected_format_id=selected_format_id, format_type=self.format_type
        )
        dm.add_job(job)
        started = dm.start_download(job.id)
        if not started:
            self.show_popup("Error", "Could not start the download. Please try again.")
            return
        self.manager.current = 'downloads'

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg), size_hint=(0.85, 0.25))
        pop.open()


class DownloadsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()
        Clock.schedule_interval(self.refresh_queue_view, 0.8)

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        title = Label(text="Active Tasks Panel", font_size=sp(21), bold=True, size_hint_y=None, height=dp(40))
        layout.add_widget(title)

        scroll = ScrollView(bar_width=dp(4))
        self.queue_list = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        self.queue_list.bind(minimum_height=self.queue_list.setter('height'))
        scroll.add_widget(self.queue_list)
        layout.add_widget(scroll)

        back_btn = RoundedButton(
            text='Back to Search Panel', size_hint_y=None, height=dp(46),
            bg_color=(0.12, 0.12, 0.16, 1), color=TEXT_WHITE
        )
        back_btn.bind(on_press=self.go_back)
        layout.add_widget(back_btn)
        self.add_widget(layout)

    def refresh_queue_view(self, dt):
        if not self.manager or self.manager.current != 'downloads':
            return

        self.queue_list.clear_widgets()
        jobs = DownloadManager().jobs

        if not jobs:
            self.queue_list.add_widget(Label(text="Your download queue is empty.", color=TEXT_MUTED, font_size=sp(13), size_hint_y=None, height=dp(100)))
            return

        for job in jobs:
            card_height = dp(105) if job.status != 'error' else dp(125)
            card = FluentCard(orientation='vertical', size_hint_y=None, height=card_height, padding=dp(12), spacing=dp(6))

            meta_box = BoxLayout(orientation='horizontal')
            meta_box.add_widget(Label(text=job.title[:28] + "...", font_size=sp(13), bold=True, halign='left', size_hint_x=0.7))
            meta_box.children[0].bind(size=meta_box.children[0].setter('text_size'))

            status_text = f"{int(job.progress)}% • {job.speed}" if job.status == 'downloading' else job.status.upper()
            meta_box.add_widget(Label(text=status_text, font_size=sp(11), color=PRIMARY_COLOR, halign='right', size_hint_x=0.3))
            card.add_widget(meta_box)

            pbar = ProgressBar(value=job.progress, max=100, size_hint_y=None, height=dp(6))
            card.add_widget(pbar)

            ctrls = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(30))
            if job.status == 'downloading':
                stop_btn = RoundedButton(text='Cancel', bg_color=(0.7, 0.2, 0.2, 1), font_size=sp(11))
                stop_btn.bind(on_press=lambda x, j_id=job.id: DownloadManager().cancel_download(j_id))
                ctrls.add_widget(stop_btn)
            elif job.status == 'done':
                success_lbl = Label(text="✓ Saved to Downloads", color=SUCCESS_GREEN, font_size=sp(11))
                ctrls.add_widget(success_lbl)
            elif job.status == 'error':
                err_lbl = Label(text="Download failed", color=(0.9, 0.3, 0.3, 1), font_size=sp(11))
                ctrls.add_widget(err_lbl)

            remove_btn = RoundedButton(text='Remove Log', bg_color=(0.22, 0.22, 0.26, 1), font_size=sp(11), size_hint_x=0.4)
            remove_btn.bind(on_press=lambda x, j_id=job.id: DownloadManager().remove_job(j_id))
            ctrls.add_widget(remove_btn)

            card.add_widget(ctrls)

            if job.status == 'error' and job.error:
                err_detail = Label(
                    text=job.error[:90], font_size=sp(10), color=(0.9, 0.55, 0.55, 1),
                    halign='left', valign='top', size_hint_y=None, height=dp(28)
                )
                err_detail.bind(size=err_detail.setter('text_size'))
                card.add_widget(err_detail)

            self.queue_list.add_widget(card)

    def go_back(self, instance):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'main'


class DownKazeApp(App):
    def build(self):
        sm = ScreenManager(transition=SlideTransition(direction='left'))
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(DownloadsScreen(name='downloads'))
        return sm

    def on_start(self):
        if platform == 'android':
            try:
                from jnius import autoclass
                from android.permissions import request_permissions, Permission
                BuildVersion = autoclass('android.os.Build$VERSION')
                sdk_int = BuildVersion.SDK_INT
                # على أندرويد 10 (API 29) فأعلى، الحفظ يتم عبر MediaStore الذي
                # لا يحتاج أي إذن تخزين وقت التشغيل، لذلك لا داعي لطلب الإذن هناك
                # (وهذا سبب عدم ظهور أي نافذة أذونات سابقاً على الأجهزة الحديثة)
                if sdk_int < 29:
                    request_permissions([
                        Permission.WRITE_EXTERNAL_STORAGE,
                        Permission.READ_EXTERNAL_STORAGE
                    ])
            except Exception as e:
                print(f"Permissions request failed: {e}")


if __name__ == '__main__':
    DownKazeApp().run()
