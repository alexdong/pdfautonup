#!/usr/bin/env python3

# Copyright Louis Paternault 2011-2014
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>. 1

"""TODO"""

from collections import namedtuple
from fractions import gcd
import PyPDF2
import logging
import os
import sys

from pdfautonup import errors, paper, options

LOGGER = logging.getLogger(__name__)

def lcm(a, b):
    return a * b / gcd(a, b)

class PageIterator:

    def __init__(self, *files):
        self.files = files

    def __iter__(self):
        for pdf in self.files:
            for num in range(pdf.numPages):
                yield pdf.getPage(num)

    def __len__(self):
        return sum([pdf.numPages for pdf in self.files])

    def repeat_iterator(self, num):
        for i in range(int(num)//len(self)):
            yield from self

class DestinationFile:

    Fit = namedtuple('Fit', ['width', 'height', 'target_size'])

    def __init__(self, source_size, target_size, interactive=False):

        self.source_size = source_size
        self.interactive = interactive


        self.width, self.height, self.target_size = min(
                self.fit(source_size, target_size),
                self.fit(source_size, (target_size[1], target_size[0])),
                key=self.wasted,
                )

        self.pdf = PyPDF2.PdfFileWriter()
        self.current_pagenum = 0
        self.current_page = None

    def wasted(self, fit):
        return abs(
                fit.target_size[0]*fit.target_size[1]
                -
                self.source_size[0]*self.source_size[1]*fit.width*fit.height
                )

    def fit(self, source_size, target_size):
        width = round(target_size[0] / source_size[0])
        height = round(target_size[1] / source_size[1])
        return self.Fit(width, height, target_size)

    @property
    def pages_per_page(self):
        return self.width * self.height

    def cell_center(self, num):
        return (
                self.target_size[0] * (self.current_pagenum % self.width) / self.width,
                self.target_size[1] * (self.height - 1 - self.current_pagenum // self.width) / self.height,
                )

    def add_page(self, page):
        if self.current_pagenum == 0:
            self.current_page = self.pdf.addBlankPage(width = self.target_size[0], height = self.target_size[1])
        (x, y) = self.cell_center(self.current_pagenum)
        self.current_page.mergeTranslatedPage(
                page,
                x,
                y,
                )
        self.current_pagenum = (self.current_pagenum + 1) % self.pages_per_page

    def write(self, filename):
        if self.interactive and os.path.exists(filename):
            if input("File {} already exists. Overwrite? ".format(filename)).lower() != "y":
                raise errors.UserCancel()
        self.pdf.write(open(filename, 'w+b'))

def rectangle_size(rectangle):
    return (
            rectangle.upperRight[0] - rectangle.lowerLeft[0],
            rectangle.upperRight[1] - rectangle.lowerLeft[1],
            )

def main():
    """Main function"""
    arguments = options.commandline_parser().parse_args(sys.argv[1:])

    pages = PageIterator(*[
        PyPDF2.PdfFileReader(pdf)
        for pdf
        in arguments.files
        ])

    page_sizes = set([rectangle_size(page.mediaBox) for page in pages])

    if len(page_sizes) != 1:
        raise errors.DifferentPageSizes()

    source_size = page_sizes.pop()
    target_size = paper.target_paper_size(getattr(arguments, 'target_size', None))

    dest = DestinationFile(
            source_size,
            target_size,
            interactive=arguments.interactive,
            )

    for page in pages.repeat_iterator(lcm(dest.pages_per_page, len(pages))):
        dest.add_page(page)

    dest.write(options.destination_name(arguments.output, arguments.files[0]))

if __name__ == "__main__":
    main()
