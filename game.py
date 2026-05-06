import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import random
import os

class DifferenceRegion:
    def __init__(self, x, y, width, height, alteration_type):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.alteration_type = alteration_type
        self.found = False
        self.center_x = x + width // 2
        self.center_y = y + height // 2

    def contains_point(self, px, py, tolerance=40):
        return (abs(px - self.center_x) <= self.width // 2 + tolerance and
                abs(py - self.center_y) <= self.height // 2 + tolerance)

    def mark_found(self):
        self.found = True

class ImageProcessor:
    NUM_DIFFERENCES = 5
    MIN_REGION_SIZE = 40
    MAX_REGION_SIZE = 80

    ALTERATION_TYPES = ["colour_shift", "brightness_patch", "noise_patch",
                        "blur_patch", "channel_swap"]

    def __init__(self):
        self.original_image = None
        self.modified_image = None
        self.difference_regions = []

    def load_image(self, path):
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Cannot read image from: {path}")
        self.original_image = img
        self.modified_image = None
        self.difference_regions = []

    def generate_differences(self):
        if self.original_image is None:
            raise RuntimeError("No image loaded")

        self.modified_image = self.original_image.copy()
        self.difference_regions = []
        h, w = self.original_image.shape[:2]

        min_margin = 20
        attempts = 0
        max_attempts = 500

        while len(self.difference_regions) < self.NUM_DIFFERENCES and attempts < max_attempts:
            attempts += 1
            rw = random.randint(self.MIN_REGION_SIZE, self.MAX_REGION_SIZE)
            rh = random.randint(self.MIN_REGION_SIZE, self.MAX_REGION_SIZE)
            rx = random.randint(min_margin, w - rw - min_margin)
            ry = random.randint(min_margin, h - rh - min_margin)

            if self._overlaps_existing(rx, ry, rw, rh):
                continue

            alt_type = random.choice(self.ALTERATION_TYPES)
            self._apply_alteration(rx, ry, rw, rh, alt_type)
            region = DifferenceRegion(rx, ry, rw, rh, alt_type)
            self.difference_regions.append(region)

        if len(self.difference_regions) < self.NUM_DIFFERENCES:
            raise RuntimeError("Could not place all differences — try a larger image")

    def _overlaps_existing(self, rx, ry, rw, rh, padding=20):
        for region in self.difference_regions:
            if not (rx + rw + padding < region.x or
                    rx > region.x + region.width + padding or
                    ry + rh + padding < region.y or
                    ry > region.y + region.height + padding):
                return True
        return False

    def _apply_alteration(self, x, y, w, h, alt_type):
        roi = self.modified_image[y:y+h, x:x+w]

        if alt_type == "colour_shift":
            shift = np.array([random.randint(30, 70) * random.choice([-1, 1]),
                              random.randint(30, 70) * random.choice([-1, 1]),
                              random.randint(30, 70) * random.choice([-1, 1])], dtype=np.int16)
            shifted = roi.astype(np.int16) + shift
            self.modified_image[y:y+h, x:x+w] = np.clip(shifted, 0, 255).astype(np.uint8)

        elif alt_type == "brightness_patch":
            factor = random.choice([0.5, 0.6, 1.5, 1.6])
            bright = roi.astype(np.float32) * factor
            self.modified_image[y:y+h, x:x+w] = np.clip(bright, 0, 255).astype(np.uint8)

        elif alt_type == "noise_patch":
            noise = np.random.randint(-40, 41, roi.shape, dtype=np.int16)
            noisy = roi.astype(np.int16) + noise
            self.modified_image[y:y+h, x:x+w] = np.clip(noisy, 0, 255).astype(np.uint8)

        elif alt_type == "blur_patch":
            blurred = cv2.GaussianBlur(roi, (15, 15), 0)
            self.modified_image[y:y+h, x:x+w] = blurred

        elif alt_type == "channel_swap":
            swapped = roi.copy()
            swapped[:, :, 0] = roi[:, :, 2]
            swapped[:, :, 2] = roi[:, :, 0]
            self.modified_image[y:y+h, x:x+w] = swapped

    def draw_circle_on_image(self, image, cx, cy, color, radius=30, thickness=3):
        result = image.copy()
        cv2.circle(result, (cx, cy), radius, color, thickness)
        return result

    def get_pil_image(self, cv_image):
        rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)


class GameState:
    MAX_MISTAKES = 3
    TOTAL_DIFFERENCES = 5

    def __init__(self):
        self.mistakes = 0
        self.found_count = 0
        self.total_score = 0
        self.game_over = False
        self.image_complete = False

    def reset_for_new_image(self):
        self.mistakes = 0
        self.found_count = 0
        self.game_over = False
        self.image_complete = False

    def record_find(self):
        self.found_count += 1
        self.total_score += 1
        if self.found_count >= self.TOTAL_DIFFERENCES:
            self.image_complete = True

    def record_mistake(self):
        self.mistakes += 1
        if self.mistakes >= self.MAX_MISTAKES:
            self.game_over = True

    def remaining(self):
        return self.TOTAL_DIFFERENCES - self.found_count

    def can_click(self):
        return not self.game_over and not self.image_complete


class SpotTheDifferenceApp(tk.Tk):
    DISPLAY_MAX_WIDTH = 500
    DISPLAY_MAX_HEIGHT = 500

    def __init__(self):
        super().__init__()
        self.title("Spot the Difference")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)

        self.processor = ImageProcessor()
        self.state = GameState()

        self.original_display = None
        self.modified_display = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self._build_ui()
        self._update_status()

    def _build_ui(self):
        header = tk.Frame(self, bg="#16213e", pady=12)
        header.pack(fill=tk.X)

        tk.Label(header, text="🔍 Spot the Difference", font=("Georgia", 22, "bold"),
                 bg="#16213e", fg="#e94560").pack()

        controls = tk.Frame(self, bg="#1a1a2e", pady=8)
        controls.pack(fill=tk.X)

        btn_style = {"font": ("Helvetica", 11, "bold"), "relief": tk.FLAT,
                     "padx": 16, "pady": 8, "cursor": "hand2", "bd": 0}

        self.load_btn = tk.Button(controls, text="📂 Load Image", bg="#0f3460",
                                  fg="white", command=self._load_image, **btn_style)
        self.load_btn.pack(side=tk.LEFT, padx=8)

        self.reveal_btn = tk.Button(controls, text="👁 Reveal All", bg="#533483",
                                    fg="white", command=self._reveal_all,
                                    state=tk.DISABLED, **btn_style)
        self.reveal_btn.pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="Load an image to begin")
        tk.Label(controls, textvariable=self.status_var, font=("Helvetica", 11),
                 bg="#1a1a2e", fg="#a8dadc").pack(side=tk.LEFT, padx=20)

        self.score_var = tk.StringVar(value="Score: 0")
        tk.Label(controls, textvariable=self.score_var, font=("Helvetica", 11, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(side=tk.RIGHT, padx=12)

        images_frame = tk.Frame(self, bg="#1a1a2e")
        images_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        left_panel = tk.Frame(images_frame, bg="#1a1a2e")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        tk.Label(left_panel, text="Original", font=("Helvetica", 12, "bold"),
                 bg="#1a1a2e", fg="#a8dadc").pack()
        self.original_canvas = tk.Canvas(left_panel, bg="#0d0d1a", bd=2,
                                         relief=tk.SUNKEN, cursor="crosshair")
        self.original_canvas.pack(fill=tk.BOTH, expand=True)

        right_panel = tk.Frame(images_frame, bg="#1a1a2e")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        tk.Label(right_panel, text="Modified — Click to find differences",
                 font=("Helvetica", 12, "bold"), bg="#1a1a2e", fg="#e94560").pack()
        self.modified_canvas = tk.Canvas(right_panel, bg="#0d0d1a", bd=2,
                                         relief=tk.SUNKEN, cursor="crosshair")
        self.modified_canvas.pack(fill=tk.BOTH, expand=True)
        self.modified_canvas.bind("<Button-1>", self._on_canvas_click)

        stats_frame = tk.Frame(self, bg="#16213e", pady=8)
        stats_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.mistakes_var = tk.StringVar(value="Mistakes: 0 / 3")
        tk.Label(stats_frame, textvariable=self.mistakes_var, font=("Helvetica", 11),
                 bg="#16213e", fg="#ffd166").pack(side=tk.LEFT, padx=16)
        self.remaining_var = tk.StringVar(value="Remaining: —")
        tk.Label(stats_frame, textvariable=self.remaining_var, font=("Helvetica", 11),
                 bg="#16213e", fg="#06d6a0").pack(side=tk.LEFT, padx=16)

    def _load_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            self.processor.load_image(path)
            self.processor.generate_differences()
            self.state.reset_for_new_image()
            self.reveal_btn.config(state=tk.NORMAL)
            self._refresh_display()
            self._update_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")

    def _refresh_display(self):
        try:
            orig_with_marks = self._draw_marks(self.processor.original_image.copy())
            mod_with_marks = self._draw_marks(self.processor.modified_image.copy())

            orig_pil = self.processor.get_pil_image(orig_with_marks)
            mod_pil = self.processor.get_pil_image(mod_with_marks)

            orig_pil, mod_pil, self.scale_factor, self.offset_x, self.offset_y = \
                self._fit_images(orig_pil, mod_pil)

            self.original_canvas.update_idletasks()
            self.modified_canvas.update_idletasks()

            self.original_display = ImageTk.PhotoImage(orig_pil)
            self.modified_display = ImageTk.PhotoImage(mod_pil)

            self.original_canvas.delete("all")
            self.modified_canvas.delete("all")

            cw = self.original_canvas.winfo_width()
            ch = self.original_canvas.winfo_height()
            if cw < 2:
                cw, ch = self.DISPLAY_MAX_WIDTH, self.DISPLAY_MAX_HEIGHT

            self.original_canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER,
                                              image=self.original_display)
            self.modified_canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER,
                                              image=self.modified_display)

            iw, ih = orig_pil.size
            self.offset_x = (cw - iw) // 2
            self.offset_y = (ch - ih) // 2
        except Exception as e:
            messagebox.showerror("Display Error", f"Could not render image:\n{e}")

    def _fit_images(self, orig_pil, mod_pil):
        self.original_canvas.update_idletasks()
        cw = max(self.original_canvas.winfo_width(), self.DISPLAY_MAX_WIDTH)
        ch = max(self.original_canvas.winfo_height(), self.DISPLAY_MAX_HEIGHT)

        w, h = orig_pil.size
        scale = min(cw / w, ch / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)

        orig_pil = orig_pil.resize((nw, nh), Image.LANCZOS)
        mod_pil = mod_pil.resize((nw, nh), Image.LANCZOS)
        return orig_pil, mod_pil, scale, 0, 0

    def _draw_marks(self, image):
        for region in self.processor.difference_regions:
            if region.found:
                cv2.circle(image, (region.center_x, region.center_y), 35,
                           (0, 0, 255), 3)
            elif hasattr(region, 'revealed') and region.revealed:
                cv2.circle(image, (region.center_x, region.center_y), 35,
                           (255, 0, 0), 3)
        return image

    def _on_canvas_click(self, event):
        if self.processor.modified_image is None:
            return
        if not self.state.can_click():
            return

        self.modified_canvas.update_idletasks()
        cw = self.modified_canvas.winfo_width()
        ch = self.modified_canvas.winfo_height()
        img_w = int(self.processor.original_image.shape[1] * self.scale_factor)
        img_h = int(self.processor.original_image.shape[0] * self.scale_factor)
        off_x = (cw - img_w) // 2
        off_y = (ch - img_h) // 2

        img_x = event.x - off_x
        img_y = event.y - off_y

        if img_x < 0 or img_y < 0 or img_x >= img_w or img_y >= img_h:
            return

        orig_x = int(img_x / self.scale_factor)
        orig_y = int(img_y / self.scale_factor)

        matched = None
        for region in self.processor.difference_regions:
            if not region.found and region.contains_point(orig_x, orig_y):
                matched = region
                break

        if matched:
            matched.mark_found()
            self.state.record_find()
            self._refresh_display()
            self._update_status()
            if self.state.image_complete:
                self._on_image_complete()
        else:
            self.state.record_mistake()
            self._flash_mistake()
            self._update_status()
            if self.state.game_over:
                self._on_game_over()

    def _flash_mistake(self):
        try:
            orig_bg = self.modified_canvas.cget("bg")
            self.modified_canvas.config(bg="#e94560")
            self.after(300, lambda: self.modified_canvas.config(bg=orig_bg))
        except Exception:
            pass

    def _reveal_all(self):
        if self.processor.modified_image is None:
            return
        for region in self.processor.difference_regions:
            if not region.found:
                region.revealed = True
        self.state.game_over = True
        self.reveal_btn.config(state=tk.DISABLED)
        self._refresh_display()
        self._update_status()
        messagebox.showinfo("Revealed", "All differences have been revealed.\nLoad a new image to play again.")

    def _on_image_complete(self):
        self.reveal_btn.config(state=tk.DISABLED)
        messagebox.showinfo("🎉 Well Done!",
                            f"You found all 5 differences!\nTotal Score: {self.state.total_score}\nLoad a new image to continue.")

    def _on_game_over(self):
        messagebox.showwarning("Game Over",
                               f"Too many mistakes! ({GameState.MAX_MISTAKES})\n"
                               f"Differences found: {self.state.found_count} / {GameState.TOTAL_DIFFERENCES}\n"
                               "Load a new image to try again.")

    def _update_status(self):
        if self.processor.modified_image is None:
            self.status_var.set("Load an image to begin")
            self.remaining_var.set("Remaining: —")
            self.mistakes_var.set("Mistakes: 0 / 3")
            return

        if self.state.image_complete:
            self.status_var.set("✅ All found! Load a new image.")
        elif self.state.game_over:
            self.status_var.set("❌ Game over — load a new image.")
        else:
            self.status_var.set("Click on the modified image to find differences")

        self.mistakes_var.set(f"Mistakes: {self.state.mistakes} / {GameState.MAX_MISTAKES}")
        self.remaining_var.set(f"Remaining: {self.state.remaining()}")
        self.score_var.set(f"Score: {self.state.total_score}")

class GameState:
    MAX_MISTAKES = 3
    TOTAL_DIFFERENCES = 5

    def __init__(self):
        self.mistakes = 0
        self.found_count = 0
        self.total_score = 0
        self.game_over = False
        self.image_complete = False

    def reset_for_new_image(self):
        self.mistakes = 0
        self.found_count = 0
        self.game_over = False
        self.image_complete = False

    def record_find(self):
        self.found_count += 1
        self.total_score += 1
        if self.found_count >= self.TOTAL_DIFFERENCES:
            self.image_complete = True

    def record_mistake(self):
        self.mistakes += 1
        if self.mistakes >= self.MAX_MISTAKES:
            self.game_over = True

    def remaining(self):
        return self.TOTAL_DIFFERENCES - self.found_count

    def can_click(self):
        return not self.game_over and not self.image_complete


class SpotTheDifferenceApp(tk.Tk):
    DISPLAY_MAX_WIDTH = 500
    DISPLAY_MAX_HEIGHT = 500

    def __init__(self):
        super().__init__()
        self.title("Spot the Difference")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)

        self.processor = ImageProcessor()
        self.state = GameState()

        self.original_display = None
        self.modified_display = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self._build_ui()
        self._update_status()

    def _build_ui(self):
        header = tk.Frame(self, bg="#16213e", pady=12)
        header.pack(fill=tk.X)

        tk.Label(header, text="🔍 Spot the Difference", font=("Georgia", 22, "bold"),
                 bg="#16213e", fg="#e94560").pack()

        controls = tk.Frame(self, bg="#1a1a2e", pady=8)
        controls.pack(fill=tk.X)

        btn_style = {"font": ("Helvetica", 11, "bold"), "relief": tk.FLAT,
                     "padx": 16, "pady": 8, "cursor": "hand2", "bd": 0}

        self.load_btn = tk.Button(controls, text="📂 Load Image", bg="#0f3460",
                                  fg="white", command=self._load_image, **btn_style)
        self.load_btn.pack(side=tk.LEFT, padx=8)

        self.reveal_btn = tk.Button(controls, text="👁 Reveal All", bg="#533483",
                                    fg="white", command=self._reveal_all,
                                    state=tk.DISABLED, **btn_style)
        self.reveal_btn.pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="Load an image to begin")
        tk.Label(controls, textvariable=self.status_var, font=("Helvetica", 11),
                 bg="#1a1a2e", fg="#a8dadc").pack(side=tk.LEFT, padx=20)

        self.score_var = tk.StringVar(value="Score: 0")
        tk.Label(controls, textvariable=self.score_var, font=("Helvetica", 11, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(side=tk.RIGHT, padx=12)

        images_frame = tk.Frame(self, bg="#1a1a2e")
        images_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        left_panel = tk.Frame(images_frame, bg="#1a1a2e")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        tk.Label(left_panel, text="Original", font=("Helvetica", 12, "bold"),
                 bg="#1a1a2e", fg="#a8dadc").pack()
        self.original_canvas = tk.Canvas(left_panel, bg="#0d0d1a", bd=2,
                                         relief=tk.SUNKEN, cursor="crosshair")
        self.original_canvas.pack(fill=tk.BOTH, expand=True)

        right_panel = tk.Frame(images_frame, bg="#1a1a2e")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        tk.Label(right_panel, text="Modified — Click to find differences",
                 font=("Helvetica", 12, "bold"), bg="#1a1a2e", fg="#e94560").pack()
        self.modified_canvas = tk.Canvas(right_panel, bg="#0d0d1a", bd=2,
                                         relief=tk.SUNKEN, cursor="crosshair")
        self.modified_canvas.pack(fill=tk.BOTH, expand=True)
        self.modified_canvas.bind("<Button-1>", self._on_canvas_click)

        stats_frame = tk.Frame(self, bg="#16213e", pady=8)
        stats_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.mistakes_var = tk.StringVar(value="Mistakes: 0 / 3")
        tk.Label(stats_frame, textvariable=self.mistakes_var, font=("Helvetica", 11),
                 bg="#16213e", fg="#ffd166").pack(side=tk.LEFT, padx=16)
        self.remaining_var = tk.StringVar(value="Remaining: —")
        tk.Label(stats_frame, textvariable=self.remaining_var, font=("Helvetica", 11),
                 bg="#16213e", fg="#06d6a0").pack(side=tk.LEFT, padx=16)

    def _load_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            self.processor.load_image(path)
            self.processor.generate_differences()
            self.state.reset_for_new_image()
            self.reveal_btn.config(state=tk.NORMAL)
            self._refresh_display()
            self._update_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")

    def _refresh_display(self):
        try:
            orig_with_marks = self._draw_marks(self.processor.original_image.copy())
            mod_with_marks = self._draw_marks(self.processor.modified_image.copy())

            orig_pil = self.processor.get_pil_image(orig_with_marks)
            mod_pil = self.processor.get_pil_image(mod_with_marks)

            orig_pil, mod_pil, self.scale_factor, self.offset_x, self.offset_y = \
                self._fit_images(orig_pil, mod_pil)

            self.original_canvas.update_idletasks()
            self.modified_canvas.update_idletasks()

            self.original_display = ImageTk.PhotoImage(orig_pil)
            self.modified_display = ImageTk.PhotoImage(mod_pil)

            self.original_canvas.delete("all")
            self.modified_canvas.delete("all")

            cw = self.original_canvas.winfo_width()
            ch = self.original_canvas.winfo_height()
            if cw < 2:
                cw, ch = self.DISPLAY_MAX_WIDTH, self.DISPLAY_MAX_HEIGHT

            self.original_canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER,
                                              image=self.original_display)
            self.modified_canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER,
                                              image=self.modified_display)

            iw, ih = orig_pil.size
            self.offset_x = (cw - iw) // 2
            self.offset_y = (ch - ih) // 2
        except Exception as e:
            messagebox.showerror("Display Error", f"Could not render image:\n{e}")

    def _fit_images(self, orig_pil, mod_pil):
        self.original_canvas.update_idletasks()
        cw = max(self.original_canvas.winfo_width(), self.DISPLAY_MAX_WIDTH)
        ch = max(self.original_canvas.winfo_height(), self.DISPLAY_MAX_HEIGHT)

        w, h = orig_pil.size
        scale = min(cw / w, ch / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)

        orig_pil = orig_pil.resize((nw, nh), Image.LANCZOS)
        mod_pil = mod_pil.resize((nw, nh), Image.LANCZOS)
        return orig_pil, mod_pil, scale, 0, 0

    def _draw_marks(self, image):
        for region in self.processor.difference_regions:
            if region.found:
                cv2.circle(image, (region.center_x, region.center_y), 35,
                           (0, 0, 255), 3)
            elif hasattr(region, 'revealed') and region.revealed:
                cv2.circle(image, (region.center_x, region.center_y), 35,
                           (255, 0, 0), 3)
        return image

    def _on_canvas_click(self, event):
        if self.processor.modified_image is None:
            return
        if not self.state.can_click():
            return

        self.modified_canvas.update_idletasks()
        cw = self.modified_canvas.winfo_width()
        ch = self.modified_canvas.winfo_height()
        img_w = int(self.processor.original_image.shape[1] * self.scale_factor)
        img_h = int(self.processor.original_image.shape[0] * self.scale_factor)
        off_x = (cw - img_w) // 2
        off_y = (ch - img_h) // 2

        img_x = event.x - off_x
        img_y = event.y - off_y

        if img_x < 0 or img_y < 0 or img_x >= img_w or img_y >= img_h:
            return

        orig_x = int(img_x / self.scale_factor)
        orig_y = int(img_y / self.scale_factor)

        matched = None
        for region in self.processor.difference_regions:
            if not region.found and region.contains_point(orig_x, orig_y):
                matched = region
                break

        if matched:
            matched.mark_found()
            self.state.record_find()
            self._refresh_display()
            self._update_status()
            if self.state.image_complete:
                self._on_image_complete()
        else:
            self.state.record_mistake()
            self._flash_mistake()
            self._update_status()
            if self.state.game_over:
                self._on_game_over()

    def _flash_mistake(self):
        try:
            orig_bg = self.modified_canvas.cget("bg")
            self.modified_canvas.config(bg="#e94560")
            self.after(300, lambda: self.modified_canvas.config(bg=orig_bg))
        except Exception:
            pass

    def _reveal_all(self):
        if self.processor.modified_image is None:
            return
        for region in self.processor.difference_regions:
            if not region.found:
                region.revealed = True
        self.state.game_over = True
        self.reveal_btn.config(state=tk.DISABLED)
        self._refresh_display()
        self._update_status()
        messagebox.showinfo("Revealed", "All differences have been revealed.\nLoad a new image to play again.")

    def _on_image_complete(self):
        self.reveal_btn.config(state=tk.DISABLED)
        messagebox.showinfo("🎉 Well Done!",
                            f"You found all 5 differences!\nTotal Score: {self.state.total_score}\nLoad a new image to continue.")

    def _on_game_over(self):
        messagebox.showwarning("Game Over",
                               f"Too many mistakes! ({GameState.MAX_MISTAKES})\n"
                               f"Differences found: {self.state.found_count} / {GameState.TOTAL_DIFFERENCES}\n"
                               "Load a new image to try again.")

    def _update_status(self):
        if self.processor.modified_image is None:
            self.status_var.set("Load an image to begin")
            self.remaining_var.set("Remaining: —")
            self.mistakes_var.set("Mistakes: 0 / 3")
            return

        if self.state.image_complete:
            self.status_var.set("✅ All found! Load a new image.")
        elif self.state.game_over:
            self.status_var.set("❌ Game over — load a new image.")
        else:
            self.status_var.set("Click on the modified image to find differences")

        self.mistakes_var.set(f"Mistakes: {self.state.mistakes} / {GameState.MAX_MISTAKES}")
        self.remaining_var.set(f"Remaining: {self.state.remaining()}")
        self.score_var.set(f"Score: {self.state.total_score}")

def main():
    try:
        app = SpotTheDifferenceApp()
        app.geometry("1100x700")
        app.mainloop()s
    except Exception as e:
        print(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
