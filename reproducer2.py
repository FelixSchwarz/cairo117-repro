
import cairocffi as cairo

from weasyprint import Document
from weasyprint.css.counters import CounterStyle
from weasyprint.draw import stacked, draw_background_image, rounded_box_path,\
    draw_inline_level
from weasyprint.fonts import FontConfiguration
from weasyprint.formatting_structure.build import build_formatting_structure
from weasyprint.layout import layout_document
from weasyprint.stacking import StackingContext
from weasyprint.tests.test_draw import parse_pixels, assert_pixels_equal
from weasyprint.tests.testing_utils import FakeHTML, resource_filename
from weasyprint.formatting_structure import boxes


def test_float_inline():
    html = '''
      <style>
        @font-face {src: url(AHEM____.TTF); font-family: ahem}
        @page {
          size: 9px 7px;
          background: white;
        }
        body {
          color: red;
          font-family: ahem;
          font-size: 2px;
        }
        div {
          line-height: 1;
          margin: 1px;
          overflow: hidden;
          width: 3.5em;
        }
      </style>
      <div>abcde</div>
      <div style="white-space: nowrap">a bcde</div>'''
    pixels = render(html)

    expected_width = 9
    expected_height = 7
    expected_pixels = b''.join(parse_pixels('''
        _________
        _RRRRRRR_
        _RRRRRRR_
        _________
        _RR__RRR_
        _RR__RRR_
        _________
    '''
    ))
    assert_pixels_equal(
        'reproducer2', expected_width, expected_height, pixels, expected_pixels)
    print('success!')


def render(html):
    dummy_fn = resource_filename('<test>')
    document = FakeHTML(string=html, base_url=dummy_fn)

    enable_hinting = True
    font_config = FontConfiguration()
    counter_style = CounterStyle()

    context = Document._build_layout_context(
        document, stylesheets=None, enable_hinting=enable_hinting,
        font_config=font_config, counter_style=counter_style)

    root_box = build_formatting_structure(
        document.etree_element, context.style_for, context.get_image_from_uri,
        document.base_url, context.target_collector, counter_style)

    page_box, = layout_document(document, root_box, context)
    surface = write_image_surface(page_box, enable_hinting)
    return surface

def write_image_surface(page_box, enable_hinting):
    width = int(page_box.margin_width())
    height = int(page_box.margin_height())

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cairo_context = cairo.Context(surface)
    with stacked(cairo_context):
        stacking_context = StackingContext.from_page(page_box)
        draw_background(
            cairo_context, stacking_context.box.background, enable_hinting)
        draw_stacking_context(cairo_context, stacking_context, enable_hinting)

    pixels = surface.get_data()[:]
    return pixels

def draw_background(context, bg, enable_hinting):
    with stacked(context):
        if enable_hinting:
            # Prefer crisp edges on background rectangles.
            context.set_antialias(cairo.ANTIALIAS_NONE)

        with stacked(context):
            painting_area = bg.layers[-1].painting_area
            context.rectangle(*painting_area)
            context.clip()
            context.set_source_rgba(*bg.color)
            context.paint()

        # Paint in reversed order: first layer is "closest" to the viewer.
        for layer in reversed(bg.layers):
            draw_background_image(context, layer, bg.image_rendering)


def draw_stacking_context(context, stacking_context, enable_hinting):
    """Draw a ``stacking_context`` on ``context``."""
    # See http://www.w3.org/TR/CSS2/zindex.html
    with stacked(context):
        box = stacking_context.box

        with stacked(context):
            # dont clip the PageBox, see #35
            if box.style['overflow'] != 'visible' and not isinstance(box, boxes.PageBox):
                # Only clip the content and the children:
                # - the background is already clipped
                # - the border must *not* be clipped
                rounded_box_path(context, box.rounded_padding_box())
                context.clip()

            # Point 7
            for block in [box] + stacking_context.blocks_and_cells:
                for child in block.children:
                    if isinstance(child, boxes.LineBox):
                        draw_inline_level(
                            context, stacking_context.page, child,
                            enable_hinting)

            # Point 8
            for child_context in stacking_context.zero_z_contexts:
                draw_stacking_context(context, child_context, enable_hinting)


if __name__ == '__main__':
    test_float_inline()

