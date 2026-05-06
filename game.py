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


