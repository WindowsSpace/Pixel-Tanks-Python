import random

#
def generate_lives_positions(lives_count):
    positions = [(x, y) for x in range(4) for y in range(4)]
    return random.sample(positions, min(lives_count, 16))