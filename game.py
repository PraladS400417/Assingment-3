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









def main():
    try:
        app = SpotTheDifferenceApp()
        app.geometry("1100x700")
        app.mainloop()
    except Exception as e:
        print(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
