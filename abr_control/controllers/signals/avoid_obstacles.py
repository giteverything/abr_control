import numpy as np

class Signal():
    """ Implements an obstacle avoidance algorithm from (Khatib, 1987).
    """

    def __init__(self, robot_config, obstacles=[], threshold=.2):

        self.robot_config = robot_config
        # set of obstacles [[x, y, radius], ...]
        self.threshold = threshold

    def generate(self, q, obstacles=[]):  # noqa901
        """ Generates the control signal

        q np.array: the current joint angles
        """

        u_psp = np.zeros(self.robot_config.num_joints)

        # calculate the inertia matrix in joint space
        Mq = self.robot_config.Mq(q)

        # add in obstacles avoidance
        for obstacle in obstacles:
            # our vertex of interest is the center point of the obstacle
            v = np.array(obstacle[:3])

            # find the closest point of each link to the obstacle
            for ii in range(self.robot_config.num_joints):
                # get the start and end-points of the arm segment
                p1 = self.robot_config.Tx('joint%i' % ii, q=q)
                if ii == self.robot_config.num_joints - 1:
                    p2 = self.robot_config.Tx('EE', q=q)
                else:
                    p2 = self.robot_config.Tx('joint%i' % (ii + 1), q=q)

                # calculate minimum distance from arm segment to obstacle
                # the vector of our line
                vec_line = p2 - p1
                # the vector from the obstacle to the first line point
                vec_ob_line = v - p1
                # calculate the projection normalized by length of arm segment
                projection = np.dot(vec_ob_line, vec_line) / np.sum((vec_line)**2)
                if projection < 0:
                    # then closest point is the start of the segment
                    closest = p1
                elif projection > 1:
                    # then closest point is the end of the segment
                    closest = p2
                else:
                    closest = p1 + projection * vec_line
                # calculate distance from obstacle vertex to the closest point
                dist = np.sqrt(np.sum((v - closest)**2))
                # account for size of obstacle
                rho = dist - obstacle[3]

                if rho < self.threshold:

                    eta = .02  # feel like i saw 4 somewhere in the paper
                    drhodx = (v - closest) / rho
                    Fpsp = (eta * (1.0/rho - 1.0/self.threshold) *
                            1.0/rho**2 * drhodx)

                    # get offset of closest point from link's reference frame
                    T_inv = self.robot_config.T_inv('link%i' % ii, q=q)
                    m = np.dot(T_inv, np.hstack([closest, [1]]))[:-1]
                    # calculate the Jacobian for this point
                    Jpsp = self.robot_config.J('link%i' % ii, x=m, q=q)[:3]

                    # calculate the inertia matrix for the
                    # point subjected to the potential space
                    Mxpsp_inv = np.dot(Jpsp,
                                       np.dot(np.linalg.pinv(Mq), Jpsp.T))
                    svd_u, svd_s, svd_v = np.linalg.svd(Mxpsp_inv)
                    # cut off singular values that could cause problems
                    singularity_thresh = .00025
                    for ii in range(len(svd_s)):
                        svd_s[ii] = 0 if svd_s[ii] < singularity_thresh else \
                            1./float(svd_s[ii])
                    # numpy returns U,S,V.T, so have to transpose both here
                    Mxpsp = np.dot(svd_v.T, np.dot(np.diag(svd_s), svd_u.T))

                    u_psp += -np.dot(Jpsp.T, np.dot(Mxpsp, Fpsp))

        return u_psp