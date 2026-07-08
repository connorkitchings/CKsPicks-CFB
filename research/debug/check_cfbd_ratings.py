import inspect

import cfbd


def check_ratings_api():
    print("Methods in RatingsApi:")
    for method_name, method in inspect.getmembers(
        cfbd.RatingsApi, predicate=inspect.isfunction
    ):
        print(method_name)

    print("\nDocstring for get_sp:")
    print(cfbd.RatingsApi.get_sp.__doc__)
    print("\nDocstring for get_fpi:")
    print(cfbd.RatingsApi.get_fpi.__doc__)


if __name__ == "__main__":
    check_ratings_api()
