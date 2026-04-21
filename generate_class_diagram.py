import os

from aspose.diagram import Diagram, SaveFileFormat


def add_class_box(page, x, y, width, height, title, attributes, methods):
    shape_id = page.draw_rectangle(x, y, width, height)
    shape = page.shapes.get_shape(shape_id)
    lines = [title, "-" * 18]
    lines.extend(attributes)
    lines.append("-" * 18)
    lines.extend(methods)
    shape.text.value.set_whole_text("\n".join(lines))
    try:
        shape.fill.fill_foregnd.value = "#FFF2CC"
        shape.line.line_weight.value = 0.02
    except Exception:
        pass
    return shape_id


def generate_class_diagram(output_path):
    diagram = Diagram()
    page = diagram.pages[0]

    upper_pc = add_class_box(
        page,
        4.5,
        8.0,
        2.6,
        1.5,
        "UpperPcWin",
        ["- leftBtnDict", "- rightPageDict"],
        ["+ initUi()", "+ AddSubWin(widgetObj)"],
    )
    square_power = add_class_box(
        page,
        1.0,
        4.8,
        2.8,
        1.6,
        "SquarePower",
        ["- isConnected", "- isOutput"],
        ["+ power_port_open()", "+ output_open()"],
    )
    long_power = add_class_box(
        page,
        6.2,
        4.8,
        2.8,
        1.6,
        "LongPower",
        ["- CurrentV", "- CurrentI"],
        ["+ start_deflection()", "+ output_open()"],
    )

    page.draw_line(5.1, 7.2, 2.4, 6.4)
    page.draw_line(6.5, 7.2, 7.6, 6.4)

    try:
        page.shapes.get_shape(upper_pc).fill.fill_foregnd.value = "#D9EAF7"
        page.shapes.get_shape(square_power).fill.fill_foregnd.value = "#E2F0D9"
        page.shapes.get_shape(long_power).fill.fill_foregnd.value = "#FCE4D6"
    except Exception:
        pass

    diagram.save(output_path, SaveFileFormat.VSDX)
    return output_path


if __name__ == "__main__":
    target = os.path.abspath("simple_class_diagram.vsdx")
    result = generate_class_diagram(target)
    print(result)
