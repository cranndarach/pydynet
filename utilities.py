from numpy.random import randint

def randchoice(l):
    """
    Returns an element from list l chosen at random.
    """
    return l[randint(len(l))]