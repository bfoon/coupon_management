def is_divisible(x, y):
    if x % y ==0:
        return True
    else:
        return False

# The is_power function will take two arguments
def is_power(x, y):
    if y == 1:
# One is the only integer that is the power of itself.
        if x == 1:
            return True
        else:
            return False
    if x < y:
      return False
    if x == y:
        return True
    if not is_divisible(x, y):
        return False
    else:
        # make recursive call
        return is_power((x / y), y)

# Print results
print("is_power(10, 2) returns: ", is_power(10, 2))
print("is_power(27, 3) returns: ", is_power(27, 3))
print("is_power(1, 1) returns: ", is_power(1, 1))
print("is_power(10, 1) returns: ", is_power(10, 1))
print("is_power(3, 3) returns: ", is_power(3, 3))
