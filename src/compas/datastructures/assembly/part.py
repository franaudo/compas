from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from collections import deque
# from functools import reduce

from compas.geometry import Frame
from compas.geometry import Polyhedron as Shape
from compas.geometry import Transformation
# from compas.geometry import multiply_matrices
from compas.geometry import boolean_union_mesh_mesh
from compas.geometry import boolean_difference_mesh_mesh
from compas.geometry import boolean_intersection_mesh_mesh

from ..datastructure import Datastructure
from ..mesh import Mesh

from .exceptions import FeatureError


class Part(Datastructure):
    """A data structure for representing assembly parts.

    Parameters
    ----------
    name : str, optional
        The name of the part.
        The name will be stored in :attr:`Part.attributes`.
    frame : :class:`compas.geometry.Frame`, optional
        The local coordinate system of the part.
    shape : :class:`compas.geometry.Shape`, optional
        The base shape of the part geometry.
    features : list of tuple(:class:`compas.geometry.Shape`, str), optional
        The features to be added to the base shape of the part geometry.

    Attributes
    ----------
    attributes : dict
        General object attributes that will be included in the data dict.
    key : int or str
        The identifier of the part in the connectivity graph of the parent assembly.
    frame : :class:`compas.geometry.Frame`
        The local coordinate system of the part.
    shape : :class:`compas.geometry.Shape`
        The base shape of the part geometry.
    features : list of tuple(:class:`compas.geometry.Shape`, str)
        The features added to the base shape of the part geometry.
    transformations : deque of :class:`compas.geometry.Transformation`
        The stack of transformations applied to the part geometry.
        The most recent transformation is on the left of the stack.
        All transformations are with respect to the local coordinate system.
    """

    operations = {
        'union': boolean_union_mesh_mesh,
        'difference': boolean_difference_mesh_mesh,
        'intersection': boolean_intersection_mesh_mesh
    }

    @property
    def DATASCHEMA(self):
        import schema
        return schema.Schema({
            "attributes": dict,
            "key": int,
            "frame": Frame,
            "shape": Shape,
            "features": list,
            "transformations": list,
        })

    @property
    def JSONSCHEMANAME(self):
        return 'part'

    def __init__(self, name, frame=None, shape=None, features=None, **kwargs):
        super(Part, self).__init__()
        self._frame = None
        self.attributes = {'name': name or 'Part'}
        self.key = None
        self.frame = frame
        self.shape = shape or Shape([], [])
        self.features = features or []
        self.transformations = deque()

    def __str__(self):
        tpl = "<Part with shape {} and features {}>"
        return tpl.format(self.shape, self.features)

    @property
    def data(self):
        """dict : A data dict representing the part attributes, the assembly graph identifier, the local coordinate system,
        the base shape, the shape features, and the transformation tack wrt to the local coordinate system.
        """
        data = {
            'attributes': self.attributes,
            "key": self.key,
            "frame": self.frame.data,
            "shape": self.shape.data,
            "features": [(shape.data, operation) for shape, operation in self.features],
            "transformations": [T.data for T in self.transformations],
        }
        return data

    @data.setter
    def data(self, data):
        self.attributes.update(data['attributes'] or {})
        self.key = data['key']
        self.frame.data = data['frame']
        self.shape.data = data['shape']
        self.features = [(Shape.from_data(shape), operation) for shape, operation in data['features']]
        self.transformations = deque([Transformation.from_data(T) for T in data['transformations']])

    @property
    def frame(self):
        if not self._frame:
            self._frame = Frame.worldXY()
        return self._frame

    @frame.setter
    def frame(self, frame):
        self._frame = frame

    @property
    def geometry(self):
        # this is a temp solution
        A = Mesh.from_shape(self.shape)
        for shape, operation in self.features:
            A.quads_to_triangles()
            B = Mesh.from_shape(shape)
            B.quads_to_triangles()
            A = Part.operations[operation](A.to_vertices_and_faces(), B.to_vertices_and_faces())
        geometry = Shape(*A)
        T = Transformation.from_frame_to_frame(Frame.worldXY(), self.frame)
        geometry.transform(T)
        return geometry

    def transform(self, T):
        """Transform the part with respect to the local cooordinate system.

        Parameters
        ----------
        T : :class:`compas.geometry.Transformation`
        """
        self.transformations.appendleft(T)
        self.shape.transform(T)
        for shape, operation in self.features:
            shape.transform(T)

    def add_feature(self, shape, operation):
        """Add a feature to the shape of the part and the operation through which it should be integrated.

        Parameters
        ----------
        shape : :class:`compas.geometry.Shape`
            The shape of the feature.
        operation : {'union', 'difference', 'intersection'}
            The boolean operation through which the feature should be integrated in the base shape.
        """
        if operation not in Part.operations:
            raise FeatureError
        self.features.append((shape, operation))

    # def apply_transformations(self):
    #     """Apply all transformations to the part shape."""
    #     X = Transformation.from_frame(self.frame)
    #     transformations = self.transformations[:]
    #     transformations.append(X)
    #     T = reduce(multiply_matrices, transformations)
    #     self.shape.transform(T)

    def to_mesh(self, cls=None):
        """Convert the part geometry to a mesh.

        Parameters
        ----------
        cls : :class:`compas.datastructures.Mesh`, optional
            The type of mesh to be used for the conversion.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            The resulting mesh.
        """
        cls = cls or Mesh
        return cls.from_shape(self.geometry)
