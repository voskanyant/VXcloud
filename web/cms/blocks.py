from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class StepsItemBlock(blocks.StructBlock):
    step_title_bold = blocks.CharBlock(required=True)
    step_text = blocks.TextBlock(required=True)
    link_text = blocks.CharBlock(required=False)
    link_url = blocks.URLBlock(required=False)


class StepsBlock(blocks.StructBlock):
    h2 = blocks.CharBlock(required=True)
    steps = blocks.ListBlock(StepsItemBlock(), required=True)


class HowToStepItemBlock(blocks.StructBlock):
    title_bold = blocks.CharBlock(required=True)
    text_rich = blocks.RichTextBlock(required=True)
    image = ImageChooserBlock(required=False)
    # Optional for decorative images and cases where surrounding text is sufficient.
    alt_text = blocks.CharBlock(
        required=False,
        help_text="Опишите смысл изображения для скринридеров. Оставьте пустым, если изображение декоративное.",
    )
    caption = blocks.CharBlock(required=False)


class HowToStepsBlock(blocks.StructBlock):
    h2 = blocks.CharBlock(required=True)
    steps = blocks.ListBlock(HowToStepItemBlock(), required=True)
