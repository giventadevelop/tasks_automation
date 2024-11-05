import sys

print('Hello, Python')

print(sys.version)

x = int(False)
print('x ', x)

str(1 + 1)

print(str(1 + 1))

print("123".replace("12", "ab"))

x = 1 / 1
print(x)

x = 'Fun Python'
var = x[0:5]
print(var)

x = 1 / 1

print(type(x))

var = [1, 2, 3] + [1, 1, 1]
print(var)
A = [1]
A.append([2,3,4,5])
print(len(A))

A = (1,2,3,4,5)
print(A[1:4])

A = ((11,12),[21,22])
print(A[1])

A = ((1),[2,3],[4])
print(A[2])

A = ["hard rock", 10, 1.2]
del (A[1])
print(A)

print(len(("disco",10)))

V = {'1', '2'}
V.add('3')
print('V ', V)

 #1=2 syntax error

'a' == 'A'
print('a' == 'A')

print(len(['A','B',1]))

print(len([sum([1,1,1])]))

x = "Go"
if x == "Go":
    print('Go')
else:
    print('Stop')
print('Mike')

x = 1
x = x > -5

print(x)

x = 0
while x < 2:
    print(x)
    x = x + 1


class Points(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y


    def print_point(self):
        print('x=', self.x, ' y=', self.y)


p1 = Points("A", "B")
p1.print_point()

for i, x in enumerate(['A', 'B', 'C']):
    print(i, 2 * x)

class Points(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def print_point(self):
        print('x=', self.x, ' y=', self.y)


p2 = Points(1, 2)
p2.x = 2
p2.print_point()

def delta(x):
    if x == 0:
        y = 1
    else:
        y = 0
    return y


print(delta(0))


a = 1


def do(x):
    return x + a


print(do(1))



# def add(a, b):
#
#  c = a+b
#
#  return(c)



#
# def add(a, b):
#
#       return(sum(a, b)

#
#
# def add(a, b):
#
#      return(sum((a, b)))
# #
#
#
def add(a, b):

    return(a+b)
print(add(1,1))