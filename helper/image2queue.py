import io
import os
import time

import numpy as np
import websockets
from imageio import imread, imwrite, mimsave
from PIL import Image


def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))


class PixPlace:
    def __init__(self, fp, name, setup=True, setpixels=None, pil_img: Image.Image | None = None):
        self.fp = fp
        self.name = name
        self.pixel_array = None
        self.queue = []
        self.top_left_corner = []
        self.bot_right_corner = []

        self.place_board = []

        if setpixels is not None:
            self.read_setpixel_string(setpixels)
            self.size = len(self.pixel_array)
            self._set_corners()

        if pil_img is not None:
            self._remove_transparent(pil_img, 0)
            self.size = len(self.pixel_array)
            self._set_corners()

        if setup:
            self._remove_transparent()
            self.size = len(self.pixel_array)
            self._set_corners()

    def _remove_transparent(self, pil_img=None, alpha_threshold=230):
        if pil_img is None:
            img = imread(self.fp)
        else:
            img = np.array(pil_img)

        # width, height, and d is depth, which we don't need.
        width, height, d = img.shape

        # creates new array of tuples with format: (x, y, r, g, b, a)
        i, j = np.meshgrid(range(height), range(width))
        loc = np.empty((width, height, 6), dtype="int16")
        loc[:, :, 0] = i
        loc[:, :, 1] = j
        if d == 3:
            loc[:, :, 2:5] = img
            loc[:, :, 5] = 255
        else:
            loc[:, :, 2:] = img

        # remoes all pixels with alpha less than 230
        self.pixel_array = loc[(loc[:, :, 5] > alpha_threshold)]

    async def get_place(self) -> str:
        res = ""
        for i in range(10):  # retry 10 times
            async with websockets.connect("wss://websocket.battlerush.dev:9000/place", max_size=1_000_000_000) as ws:
                await ws.send(b'\x01')
                res = await ws.recv()
            if len(res) > 50:
                break
        return res

    async def get_image(self):
        bytes = await self.get_place()
        if bytes is None:
            print("No image received")
            return
        # p = imread(bytes)
        # im = Image.open(bytes)
        p = np.fromstring(bytes, np.uint8)
        p = np.reshape(p[1:], (1000, 1000, 3))
        return p

    async def add_place(self):
        arr = await self.get_image()
        arr[:, :, 0] = arr[:, :, 1] = arr[:, :, 2] = np.mean(arr, 2)
        self.place_board = arr.astype("uint8")

    def get_preview(self):
        pix = self.pixel_array
        self.place_board[pix[:, 1], pix[:, 0]] = pix[:, 2:5]
        imwrite("test.png", self.place_board)

    async def create_gif(self) -> io.BytesIO:
        await self.add_place()
        cur = 0
        rem = len(self.pixel_array)
        n = rem // 100 + 1
        x1, y1 = self.top_left_corner
        x2, y2 = self.bot_right_corner
        images = []
        blank_place = self.place_board.copy()

        while cur < rem:
            pix = self.pixel_array[cur:cur + n]
            blank_place[pix[:, 1], pix[:, 0]] = pix[:, 2:5]
            if cur + n < rem:
                cur += n
            else:
                cur += rem - cur
            # crops the gif to the image
            images.append(Image.fromarray(blank_place).crop((max(x1 - 10, 0), max(y1 - 10, 0), min(x2 + 10, 999), min(y2 + 10, 999))))
        buffer = io.BytesIO()
        images[0].save(buffer, format="GIF", append_images=images[1:], save_all=True, duration=50, loop=0)
        buffer.seek(0)
        return buffer

    def _set_corners(self):
        topX = np.amin(self.pixel_array[:, 0])
        topY = np.amin(self.pixel_array[:, 1])
        self.top_left_corner = [topX, topY]

        botX = np.amax(self.pixel_array[:, 0])
        botY = np.amax(self.pixel_array[:, 1])
        self.bot_right_corner = [botX, botY]

    def left_to_right(self):
        """
        Orders the array so that the pixels on the left are drawn first
        and adds pixel outwards.
        """
        arr = self.pixel_array

        # sorts by the x cord
        self.pixel_array = arr[np.argsort(arr[:, 0])]

    def center_first(self):
        """
        Orders the array so that the pixels in the center are drawn first
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
        self.pixel_array = n.astype("uint16")

    def perc_to_perc(self, start: int, end: int) -> int:
        drawn = int(self.size * (start / 100))
        end = int(self.size * (end / 100))
        self.pixel_array = self.pixel_array[start:end]
        self.size = len(self.pixel_array)
        self._set_corners()
        return drawn

    def end_at(self, percent: int) -> int:
        drawn = int(self.size * (percent / 100))
        self.pixel_array = self.pixel_array[:drawn]
        self.size = len(self.pixel_array)
        self._set_corners()
        return drawn

    def resume_progress(self, percent: int) -> int:
        drawn = int(self.size * (percent / 100))
        self.pixel_array = self.pixel_array[drawn:]
        self._set_corners()
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

    def read_setpixel_string(self, inp: str):
        inp = inp.replace("\r", "")
        setpixels = inp.split("\n")
        self.pixel_array = np.empty((len(setpixels), 6), dtype="int16")
        for i, pix in enumerate(setpixels):
            args = pix.split(" ")
            # .place, setpixel, x, y, #hex
            rgb = hex_to_rgb(args[4])
            self.pixel_array[i] = [args[2], args[3], rgb[0], rgb[1], rgb[2], 255]

    def load_array(self, cus_fp=None):
        if cus_fp is None:
            cus_fp = f"{self.name}.npy"
        self.pixel_array = np.load(f"{cus_fp}")
        self.size = len(self.pixel_array)
        self._set_corners()

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
        img = PixPlace(fp, "test")
        img.center_first()
        img.low_to_high_res()
    t2 = time.perf_counter()
    print(f"Time taken: {(t2 - t1) / n}s avg")


def get_all_queues(dir="./"):
    q = []
    for filename in os.listdir(dir):
        if filename.endswith(".npy"):
            img = PixPlace(filename.replace(".npy", ""), "q", setup=False)
            img.load_array(os.path.join(dir, filename))
            q.append(img)
    return q


def main():
    fp = "sponge.png"
    place = "place.png"
    # test(fp, 100)
    p = ""
    with open("toDraw.txt", "r") as f:
        p = f.read()

    img = PixPlace(fp, "t", setup=False, setpixels=p)
    print(img)
    # print(Image.open(fp).getpixel((92, 236)))


if __name__ == "__main__":
    main()
