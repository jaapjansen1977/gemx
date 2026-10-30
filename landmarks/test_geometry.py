import unittest
import numpy as np
from .geometry import attach,evaluate


class AttachmentTests(unittest.TestCase):
    def test_interior_edge_vertex_and_rigid_transform(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[0.,1,0]])
        faces=np.array([[0,1,2]])
        for seed,expected in [([.2,.3,2],[.2,.3,0]),([.8,.8,0],[.5,.5,0]),([-2,-1,0],[0,0,0])]:
            face,bary,distance=attach(np.array(seed),vertices,faces)
            point=evaluate(vertices,faces,np.array([face]),bary[None])[0]
            np.testing.assert_allclose(point,expected,atol=1e-12)
            np.testing.assert_allclose(bary.sum(),1.)
            self.assertTrue((bary>=0).all())
            rotation=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
            moved=evaluate(vertices@rotation.T+2,faces,np.array([face]),bary[None])[0]
            np.testing.assert_allclose(moved,point@rotation.T+2)

    def test_degenerate_triangle(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[1.,0,0]])
        face,bary,distance=attach(np.array([.4,1,0]),vertices,np.array([[0,1,2]]))
        np.testing.assert_allclose(bary@vertices,[.4,0,0])
        self.assertAlmostEqual(distance,1.)


if __name__=='__main__': unittest.main()
