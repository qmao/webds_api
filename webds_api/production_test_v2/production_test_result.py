import json

class TestResult:
    def __init__(self, id):
        self.results = []
        self.id = id

    def add_result(self, test_result):
        self.results.append(test_result)

    def save_results_to_json(self, filename):
        data = {
            'id': self.id,  # Include the ID as a key in the root
            'results': self.results
        }
        with open(filename, 'w') as file:
            json.dump(data, file)