class XMLTestResultGenerator(object):
    MATRIX_TYPE_LONG = None
    MATRIX_TYPE_DOUBLE = None
    MATRIX_TYPE_CSV = None

    def __init__(self):
        pass

    def set_row_headers(self, headers):
        print("[ROW]", headers)
        pass

    def set_column_headers(self, headers):
        print("[COL]", headers)
        pass

    def add_matrix(self, matrix, data_type, name):
        print("\n\n[Matrix]", matrix, data_type, name)
        pass

    def get_xml(self):
        pass
