from collections import Sequence
from io import BytesIO, StringIO
import xml.etree.ElementTree as ET

from numpy import array, int32, savetxt

FRAME_DELIMITER = ","  # hopefully won't change in the future
TYPE_MAP = {
    "INT": int,
    "UINT": int,
    "FLOAT": float,
    "UNUMBER": float,
    "NUMBER": float,
    "STRING": str,
}

# Reading
# =======
def extract_variables(tree):
    variables = {}
    inputs_node = tree.find("Inputs")
    if inputs_node is not None:
        variables_node = inputs_node.find("Variables")
        if variables_node is not None:
            for var_node in variables_node.iter("Var"):
                if var_node.get("exists")!="false":
                    var_name = var_node.get("name")
                    var_value = var_node.get("value")
                    var_type = var_node.get("type")
                    var_elements = int(var_node.get("elements"))
                    py_type = TYPE_MAP[var_type]
                    if var_elements == 1:
                        variables[var_name] = py_type(var_value)
                    else:
                        variables[var_name] = [py_type(v) for v in var_value.split(",")]
                        if len(variables[var_name]) != var_elements:
                            raise ValueError("mismatched number of elements in Variable {}: expected {}, found {}".format(var_name, var_elements, len(variables[var_name])))
    return variables

def extract_frame_collections(tree):
    collections = {}
    for collection_node in tree.iter("Collection"):
        coll_name = collection_node.get("name")
        frames = []  # could be faster to pre-allocate array, but not obvious to me how to count Frame tags without create explicit list with all contents
        for frame_node in collection_node.iter("Frame"):
            array_text = frame_node.text
            frame = array([int(x) for x in array_text.split(FRAME_DELIMITER)], dtype=int32)  # int32 should be big enough for both raw and delta
            frames.append(frame)
        collections[coll_name] = array(frames)
    return collections

def interpret_frames(metadata, frames):
    # first axis is frame index
    # separate into image, profx, and profy
    rxCount = metadata["rxCount"]
    txCount = metadata["txCount"]
    hasProfiles = metadata.get("hasProfiles", False)
    expectedLen = rxCount * txCount
    if hasProfiles:
        expectedLen += rxCount + txCount
    if len(frames) != 0 and frames.shape[1] < expectedLen:
        raise ValueError("Expected {} elements in frame; got {}.".format(expectedLen, frames.shape[1]))
    images = frames[:, :rxCount * txCount].reshape(-1, txCount, rxCount)
    if hasProfiles:
        profx = frames[:, rxCount * txCount:rxCount * txCount + rxCount]
        profy = frames[:, rxCount * txCount + rxCount:]
    else:
        profx = None
        profy = None
    return images, profx, profy

def interpret_frame_collections(metadata, collections):
    return dict((k, interpret_frames(metadata, f)) for k, f in collections.items() if f.size > 0)

def parse_xml_log(xml_fileobj):
    """
    This is meant to be quite generic, supporting arbitrary metadata and frame collections.

    Returns (metadata dict, dict of (images, profx, profy) keyed by collection name)
    """
    tree = ET.parse(xml_fileobj)
    if tree:
        metadata = extract_variables(tree)
        frame_collections = extract_frame_collections(tree)
        interpreted_frame_collections = interpret_frame_collections(metadata, frame_collections)
        return metadata, interpreted_frame_collections
    else:
        return {}, {}

def parse_xml_log_single_collection(xml_fileobj):
    metadata, interpreted_frame_collections = parse_xml_log(xml_fileobj)
    assert len(interpreted_frame_collections) == 1, "expected single collection, but found {}".format(len(interpreted_frame_collections))
    return metadata, next(iter(interpreted_frame_collections.values()))

# Writing
# =======

def serialize_array(x):
    c = BytesIO()
    savetxt(c, x.flatten()[None, :], delimiter=", ", newline="", fmt="%d")
    return c.getvalue().decode("utf-8")

def indent_elem(elem, level=0):
    """
    https://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_elem(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def serialize_xml_log(metadata, frame_collections):
    tutor = ET.Element("TutorDataSet")
    inputs = ET.SubElement(tutor, "Inputs")
    variables = ET.SubElement(inputs, "Variables")
    for k, v in metadata.items():
        if isinstance(v, Sequence):
            v_example = v[0]
            v_str = ", ".join(str(x) for x in v)  # do not recurse; do not allow nesting
            num_elem = len(v)
        else:
            v_example = v
            v_str = str(v)
            num_elem = 1
        if isinstance(v_example, float):
            v_type = "UNUMBER"
        else:
            v_type = "UINT"
        attrs = {"name": k, "value": v_str, "type": v_type, "elements": str(num_elem)}
        ET.SubElement(variables, "Var", attrs)
    for k, (image, profx, profy) in frame_collections.items():
        coll = ET.SubElement(inputs, "Collection", {"name": k})
        assert not ((profx is None) ^ (profy is None))
        if profx is None:
            for i in image:
                frame = ET.SubElement(coll, "Frame")
                frame.text = serialize_array(i)
        else:
            for i, x, y in zip(image, profx, profy):
                frame = ET.SubElement(coll, "Frame")
                frame.text = ", ".join((serialize_array(i), serialize_array(x), serialize_array(y)))
    tree = ET.ElementTree(tutor)
    indent_elem(tutor)  # make it nice for humans to read
    return tree

def xml_tree_tostring(t):
    c = BytesIO()
    t.write(c)
    return c.getvalue().decode("utf-8")

# Tests
# =======

if __name__ == "__main__":
    import unittest

    def isequal_frame(a, b):
        """
        Compare frames. Frames can be an array or None.
        """
        if (a is None) ^ (b is None):
            return False
        if (a is not None) and (a != b).any():
            return False
        return True

    def isequal_frame_coll(a, b):
        for ka, kb in zip(a.keys(), b.keys()):
            if ka != kb:
                return False
        for ((ia, xa, ya), (ib, xb, yb)) in zip(a.values(), b.values()):
            if not isequal_frame(ia, ib) or not isequal_frame(xa, xb) or not isequal_frame(ya, yb):
                return False
        return True

    class TestDS6XMLParsing(unittest.TestCase):
        def test_parse_xml_log_empty_ok(self):
            xml = StringIO(u"<TutorDataSet></TutorDataSet>")  # the emptiest you can get is one frame
            metadata, frame_coll = parse_xml_log(xml)
            self.assertTrue(metadata == dict(), "expected empty metadata")
            self.assertTrue(frame_coll == dict(), "expected empty frame collections")

        def test_parse_xml_log_metadata_only(self):
            xml = StringIO(
u"""<TutorDataSet>
    <Inputs>
        <Variables>
            <Var name="txCount" transaction="StaticConfig" value="36" displayName="Tx Count" type="UINT" elements="1" />
            <Var name="rxCount" transaction="StaticConfig" value="15" displayName="Rx Count" type="UINT" elements="1" />
        </Variables>
    </Inputs>
</TutorDataSet>""")
            metadata, frame_coll = parse_xml_log(xml)
            expected_metadata = {"txCount": 36, "rxCount": 15}
            self.assertTrue(metadata == expected_metadata, "In parsing:\n\n{}\n\nExpected metadata to be:\n\n{}\n\nGot:\n\n{}".format(xml, expected_metadata, metadata))
            self.assertTrue(frame_coll == dict(), "expected empty frame collections")

        def test_parse_xml_log_frame_collection(self):
            xml = StringIO(
u"""<TutorDataSet>
    <Inputs>
        <Variables>
            <Var name="txCount" value="2" type="UINT" elements="1"/>
            <Var name="rxCount" value="3" type="UINT" elements="1"/>
        </Variables>
        <Collection name="a">
            <Frame>1, 2, 3, 4, 5, 6</Frame>
            <Frame>7, 8, 9, 10, 11, 12</Frame>
        </Collection>
        <Collection name="b">
            <Frame>13, 14, 15, 16, 17, 18</Frame>
            <Frame>19, 20, 21, 22, 23, 24</Frame>
        </Collection>
    </Inputs>
</TutorDataSet>""")
            metadata, frame_coll = parse_xml_log(xml)
            expected_metadata = {"txCount": 2, "rxCount": 3}
            expected_frame_collection = {
                "a": (array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]], dtype=int32), None, None),
                "b": (array([[[13, 14, 15], [16, 17, 18]], [[19, 20, 21], [22, 23, 24]]], dtype=int32), None, None),
            }
            self.assertTrue(metadata == expected_metadata, "In parsing:\n\n{}\n\nExpected metadata to be:\n\n{}\n\nGot:\n\n{}".format(xml, expected_metadata, metadata))
            self.assertTrue(isequal_frame_coll(frame_coll, expected_frame_collection), "In parsing:\n\n{}\n\nExpected frame collection to be:\n\n{}\n\nGot:\n\n{}".format(xml, expected_frame_collection, frame_coll))

        def test_parse_xml_log_frame_collection_has_profiles(self):
            xml = StringIO(
u"""<TutorDataSet>
    <Inputs>
        <Variables>
            <Var name="txCount" value="2" type="UINT" elements="1"/>
            <Var name="rxCount" value="3" type="UINT" elements="1"/>
            <Var name="hasProfiles" value="1" type="UINT" elements="1"/>
        </Variables>
        <Collection name="a">
            <Frame>1, 2, 3, 4, 5, 6, 1, 2, 3, 1, 2</Frame>
            <Frame>7, 8, 9, 10, 11, 12, 4, 5, 6, 3, 4</Frame>
        </Collection>
        <Collection name="b">
            <Frame>13, 14, 15, 16, 17, 18, 7, 8, 9, 5, 6</Frame>
            <Frame>19, 20, 21, 22, 23, 24, 10, 11, 12, 7, 8</Frame>
        </Collection>
    </Inputs>
</TutorDataSet>""")
            metadata, frame_coll = parse_xml_log(xml)
            expected_metadata = {"txCount": 2, "rxCount": 3, "hasProfiles": 1}
            expected_frame_collection = {
                "a": (array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]], dtype=int32),  # image
                      array([[1, 2, 3], [4, 5, 6]], dtype=int32),                               # profx
                      array([[1, 2], [3, 4]], dtype=int32)),                                    # profy
                "b": (array([[[13, 14, 15], [16, 17, 18]], [[19, 20, 21], [22, 23, 24]]], dtype=int32),
                      array([[7, 8, 9], [10, 11, 12]], dtype=int32),
                      array([[5, 6], [7, 8]], dtype=int32))}
            self.assertTrue(metadata == expected_metadata, "In parsing:\n\n{}\n\nExpected metadata to be:\n\n{}\n\nGot:\n\n{}".format(xml, expected_metadata, metadata))
            self.assertTrue(isequal_frame_coll(frame_coll, expected_frame_collection), "In parsing:\n\n{}\n\nExpected frame collection to be:\n\n{}\n\nGot:\n\n{}".format(xml, expected_frame_collection, frame_coll))

    def xml_trees_equal(t1, t2):
        return xml_elements_equal(t1.getroot(), t2.getroot())

    def xml_elements_equal(e1, e2):
        if e1.tag != e2.tag: return False
        if e1.text != e2.text: return False
        if e1.tail != e2.tail: return False
        if e1.attrib != e2.attrib: return False
        if len(e1) != len(e2): return False
        return all(xml_elements_equal(c1, c2) for c1, c2 in zip(e1, e2))

    class TestDS6XMLWriting(unittest.TestCase):
        def test_write_xml_log_empty_ok(self):
            tree = serialize_xml_log({}, {})
            _tutor = ET.Element("TutorDataSet")
            _inputs = ET.SubElement(_tutor, "Inputs")
            expected_xml = ET.ElementTree(_tutor)
            ET.SubElement(_inputs, "Variables")
            indent_elem(_tutor)
            self.assertTrue(xml_trees_equal(tree, expected_xml), "Expected:\n\n{}\n\nGot:\n\n{}".format(xml_tree_tostring(expected_xml), xml_tree_tostring(tree)))

        def test_write_xml_log_metadata(self):
            metadata = {"a": 1, "b": 2, "c": [3, 4]}
            tree = serialize_xml_log(metadata, {})
            _tutor = ET.Element("TutorDataSet")
            _inputs = ET.SubElement(_tutor, "Inputs")
            _variables = ET.SubElement(_inputs, "Variables")
            ET.SubElement(_variables, "Var", {"name": "a", "value": "1", "type": "UINT", "elements": "1"})
            ET.SubElement(_variables, "Var", {"name": "b", "value": "2", "type": "UINT", "elements": "1"})
            ET.SubElement(_variables, "Var", {"name": "c", "value": "3, 4", "type": "UINT", "elements": "2"})
            expected_xml = ET.ElementTree(_tutor)
            indent_elem(_tutor)
            self.assertTrue(xml_trees_equal(tree, expected_xml), "Expected:\n\n{}\n\nGot:\n\n{}".format(xml_tree_tostring(expected_xml), xml_tree_tostring(tree)))

        def test_write_xml_log_trans_frames_ok(self):
            metadata = {"txCount": 2, "rxCount": 3}
            frame_collection = {
                "a": (array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]], dtype=int32), None, None),
                "b": (array([[[13, 14, 15], [16, 17, 18]], [[19, 20, 21], [22, 23, 24]]], dtype=int32), None, None),
            }
            serialize_xml_log(metadata, frame_collection)

        def test_write_xml_log_frames_ok(self):
            metadata = {"txCount": 2, "rxCount": 3, "hasProfiles": 1}
            frame_collection = {
                "a": (array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]], dtype=int32),  # image
                      array([[1, 2, 3], [4, 5, 6]], dtype=int32),                               # profx
                      array([[1, 2], [3, 4]], dtype=int32)),                                    # profy
                "b": (array([[[13, 14, 15], [16, 17, 18]], [[19, 20, 21], [22, 23, 24]]], dtype=int32),
                      array([[7, 8, 9], [10, 11, 12]], dtype=int32),
                      array([[5, 6], [7, 8]], dtype=int32))}
            serialize_xml_log(metadata, frame_collection)

    unittest.main()
