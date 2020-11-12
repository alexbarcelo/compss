#!/usr/bin/python
#
#  Copyright 2002-2019 Barcelona Supercomputing Center (www.bsc.es)
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from pycompss.api.task import task
from pycompss.api.api import compss_wait_on
from pycompss.api.parameter import COLLECTION_IN
# from pycompss.api.parameter import COLLECTION_OUT
from pycompss.api.parameter import COLLECTION_INOUT


class Poligon(object):

    def __init__(self, sides):
        self.sides = sides

    def increment(self, amount):
        self.sides += amount

    def get_sides(self):
        return self.sides


# @task(value=COLLECTION_OUT)
def generate_collection(value):
    value.append(Poligon(2))
    value.append(Poligon(10))
    value.append(Poligon(20))


@task(value=COLLECTION_INOUT)
def update_collection(value):
    for c in value:
        c.increment(1)


@task(returns=1, value=COLLECTION_IN)
def sum_all_sides(value):
    result = 0
    for c in value:
        result += c.get_sides()
    return result


def main():
    initial = []
    generate_collection(initial)
    update_collection(initial)
    result = sum_all_sides(initial)
    result = compss_wait_on(result)
    assert result == 35, "ERROR: Unexpected result (%s != 35)." % str(result)

# Uncomment for command line check:
# if __name__ == '__main__':
#     main()
