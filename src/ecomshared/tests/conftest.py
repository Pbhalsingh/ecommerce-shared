import sys, os

ecomshared = os.path.abspath("src")

sys.path.insert(0, ecomshared)
print("path is {}".format(sys.path))

def init():

    os.environ["ENVIRONMENT"] = "test"
      
    print(os.environ["ENVIRONMENT"])

init()

