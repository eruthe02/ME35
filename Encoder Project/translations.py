import numpy as np
from math import cos, sin


def rotate_around_point(x, y, cx, cy, theta):
    point = np.array([x, y, 1])
    
    # Translate to origin
    translate_to_origin_mat = np.array([
        [1, 0, -cx],
        [0, 1, -cy],
        [0, 0, 1]
    ])




    
    # Rotate
    theta_rad = (theta/180) * np.pi
    rotation_mat = np.array([
        [cos(theta_rad), -sin(theta_rad), 0],
        [sin(theta_rad), cos(theta_rad), 0],
        [0, 0, 1]
    ])

    
    # Translate back

    translate_back_mat = np.array([
        [1, 0, cx],
        [0, 1, cy],
        [0,0,1]
    ])
    [x_final, y_final, whatever] = translate_back_mat @ rotate_around_point @ translate_to_origin_mat @ point
    
    return x_final, y_final

    