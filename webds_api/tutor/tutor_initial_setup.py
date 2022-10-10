from .tutor_initial_setup_module import LocalCBC

class InitialSetup():
    def get():
        try:
            data = LocalCBC().run()
        except Exception as e:
            return {"error": str(e)}
        return {"data": data}
        
    def post(input_data):
        print(input_data)
        return input_data
