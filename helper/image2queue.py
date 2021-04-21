import numpy as np
from imageio import imread
import time
import os


class PixPlace:
    def __init__(self, fp, name, setup=True):
        self.fp = fp
        self.name = name
        self.pixel_array = None
        self.queue = []
        self.top_left_corner = []
        self.bot_right_corner = []

        if setup:
            self._remove_transparent()
            self.size = len(self.pixel_array)
            self._set_corners()

    def _remove_transparent(self):
        img = imread(self.fp)

        # width, height, and d is depth, which we don't need.
        width, height, d = img.shape

        # creates new array of tuples with format: (x, y, r, g, b, a)
        i, j = np.meshgrid(range(height), range(width))
        loc = np.empty((height, width, 6), dtype="int16")
        loc[:, :, 0] = i
        loc[:, :, 1] = j
        loc[:, :, 2:] = img

        # remoes all pixels with alpha less than 230
        self.pixel_array = loc[(loc[:, :, 5] > 230)]

    def _set_corners(self):
        topX = np.amin(self.pixel_array[:, 0])
        topY = np.amin(self.pixel_array[:, 1])
        self.top_left_corner = [topX, topY]

        botX = np.amax(self.pixel_array[:, 0])
        botY = np.amax(self.pixel_array[:, 1])
        self.bot_right_corner = [botX, botY]

    def center_first(self):
        """
        Orders the array so that the pixels in the center are draw first
        and adds pixel outwards.
        """
        arr = self.pixel_array

        # gets the cords of the image center
        ax = np.average(arr[:, 0])
        ay = np.average(arr[:, 1])

        # creates new array the same size as arr, but only depth of 3
        # each element is a 3 big array [dist_to_center, x, y]
        h, d = arr.shape
        dist_to_center = np.empty((h, 3))
        dist_to_center[:, 1:] = arr[:, 0:2]
        # calculates the distance to center and puts it into the array
        dist_to_center[:, 0] = np.sqrt((ax - dist_to_center[:, 1]) ** 2 + (ay - dist_to_center[:, 2]) ** 2)

        # gets the index order when sorted by distance to center and re-orders arr
        self.pixel_array = arr[np.argsort(dist_to_center[:, 0])]

    def low_to_high_res(self):
        """
        Makes multiple waves across the image.
        Places every 540th pixel. This works with 37 being
        a generator of 541 and results in a random looking
        placement, while it's not random at all.
        """
        n = np.empty(self.pixel_array.shape)
        t = 0
        for i in [pow(37, x, 541) - 1 for x in range(540)]:
            c = len(self.pixel_array[i::540])
            n[t:t + c] = self.pixel_array[i::540]
            t += c
        self.pixel_array = n

    def resume_progress(self, percent: int) -> int:
        drawn = int(self.size * (percent / 100))
        self.pixel_array = self.pixel_array[drawn:]
        return drawn

    def flip(self):
        """
        Flips the array. This combined with center_first() allows
        you to fill the pixels from out inwards.
        """
        self.pixel_array = np.flip(self.pixel_array, 0)

    def read_queue(self, q: list):
        self.pixel_array = np.array(q)
        self.size = len(self.pixel_array)
        self._set_corners()

    def get_queue(self):
        self.queue = self.pixel_array.tolist()
        return self.queue

    def load_array(self, cus_fp=None):
        if cus_fp is None:
            cus_fp = f"{self.name}.npy"
        self.pixel_array = np.load(f"{cus_fp}")
        self.size = len(self.pixel_array)

    def save_array(self, cus_fp=None):
        if cus_fp is None:
            cus_fp = self.name
        np.save(f"{cus_fp}.npy", self.pixel_array)

    def __repr__(self):
        return f"<PixPlace Object | Size: {self.size}>"

    def __str__(self):
        return str(self.pixel_array)


def test(fp, n):
    t1 = time.perf_counter()
    for i in range(n):
        img = PixPlace(fp)
        img.center_first()
        img.low_to_high_res()
    t2 = time.perf_counter()
    print(f"Time taken: {(t2 - t1) / n}s avg")


def get_all_queues(dir="./"):
    q = []
    for filename in os.listdir(dir):
        if filename.endswith(".npy"):
            img = PixPlace(filename.replace(".npy", ""), setup=False)
            img.load_array(os.path.join(dir, filename))
            q.append(img)
    return q


def main():
    fp = "sponge.png"
    test(fp, 100)

    """img = PixPlace(fp)
    img.center_first()
    img.save_array()
    img.load_array()
    img.flip()
    img.low_to_high_res()

    print(img)
    print(Image.open(fp).getpixel((258, 366)))"""

    """q = get_all_queues()
    for f in q:
        print(f)"""


if __name__ == "__main__":
    main()