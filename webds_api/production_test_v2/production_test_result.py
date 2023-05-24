import json

class TestResult:
    def __init__(self, id):
        self.results = []
        self.id = id
        self.time = {}
        self.plan = "default"

    def add_result(self, test_result):
        self.results.append(test_result)

    def add_time(self, time):
        self.time = time
        
    def add_plan(self, plan):
        self.plan = plan

    def save_results_to_json(self, filename):
        data = {
            'id': self.id,  # Include the ID as a key in the root
            'results': self.results,
            'time': self.time
        }
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4, sort_keys=True, default=str)

    def get_id(self):
        return self.id
        
    def get_result(self):
        status = 'pass'
        for r in self.results:
            if r["result"] != "pass":
                status = "fail"
        return status
        
    def get_time(self):
        return self.time["total"]

    def get_info(self):
        return str(self.id) + "_" + self.get_result() + "_" + self.get_time() + "_" + self.plan