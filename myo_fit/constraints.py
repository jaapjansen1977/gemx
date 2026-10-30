"""Eliminate active scalar joint equalities and propagate ALL joint bounds.

MuJoCo joint constraints: q1-q1_ref = polynomial(q2-q2_ref).
Choose a connected feasible interval containing/nearest the reference value.
This deliberately supports the inspected model, not arbitrary equality types.
"""
import numpy as np
from numpy.polynomial import Polynomial
import mujoco


class CoupledCoordinates:
    def __init__(self, model):
        self.model = model
        self.scalar = [j for j in range(model.njnt) if model.jnt_type[j] in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE)]
        self.addresses = np.array([model.jnt_qposadr[j] for j in self.scalar])
        self.dependencies = {}
        for eq in range(model.neq):
            if not model.eq_active0[eq]:
                continue
            if model.eq_type[eq] != mujoco.mjtEq.mjEQ_JOINT:
                raise ValueError('Unsupported active equality type; refusing to omit it')
            child, parent = int(model.eq_obj1id[eq]), int(model.eq_obj2id[eq])
            if child not in self.scalar or (parent >= 0 and parent not in self.scalar):
                raise ValueError('Only scalar joint equality elimination supported')
            if child in self.dependencies:
                raise ValueError('Multiple equations for the same dependent joint')
            self.dependencies[child] = (parent, model.eq_data[eq, :5].copy())
        self.independent = [j for j in self.scalar if j not in self.dependencies]
        self.root_index = {j: i for i, j in enumerate(self.independent)}
        self.reference = model.qpos0.copy()
        memo = {}
        def expression(joint, visiting=()):
            if joint in memo:
                return memo[joint]
            if joint in visiting:
                raise ValueError('Cyclic joint couplings')
            if joint not in self.dependencies:
                result = (joint, Polynomial([0., 1.]))
            else:
                parent, coefficients = self.dependencies[joint]
                ref = self.reference[model.jnt_qposadr[joint]]
                if parent < 0:
                    result = (None, Polynomial([ref + coefficients[0]]))
                else:
                    root, poly = expression(parent, (*visiting, joint))
                    parent_ref = self.reference[model.jnt_qposadr[parent]]
                    result = (root, Polynomial([ref]) + Polynomial(coefficients)(poly - parent_ref))
            memo[joint] = result
            return result
        self.expressions = {j: expression(j) for j in self.scalar}
        self.intervals = []
        self.bounds = []
        for joint in self.independent:
            if not model.jnt_limited[joint]:
                raise ValueError('Expected finite bounds for every independent scalar joint')
            low, high = model.jnt_range[joint]
            related = [(j, poly) for j, (root, poly) in self.expressions.items() if root == joint and model.jnt_limited[j]]
            points = [float(low), float(high)]
            for other, poly in related:
                for edge in model.jnt_range[other]:
                    for value in (poly - edge).roots():
                        if abs(value.imag) < 1e-8 and low < value.real < high:
                            points.append(float(value.real))
            points = sorted(set(points))
            feasible = []
            for a, b in zip(points[:-1], points[1:]):
                mid = (a + b) / 2.
                if all(model.jnt_range[j, 0] - 1e-10 <= poly(mid) <= model.jnt_range[j, 1] + 1e-10 for j, poly in related):
                    if feasible and abs(feasible[-1][1] - a) < 1e-9:
                        feasible[-1][1] = b
                    else:
                        feasible.append([a, b])
            if not feasible:
                raise ValueError(f'No feasible coupling interval for {model.joint(joint).name}')
            ref = self.reference[model.jnt_qposadr[joint]]
            chosen = min(feasible, key=lambda ab: max(ab[0] - ref, ref - ab[1], 0.))
            self.bounds.append(chosen)
            self.intervals.append({'joint': model.joint(joint).name, 'feasible_components': feasible, 'chosen': chosen})
        self.bounds = np.array(self.bounds)
        self.reference_independent = np.clip(self.reference[[model.jnt_qposadr[j] for j in self.independent]], self.bounds[:, 0], self.bounds[:, 1])
        width = max(len(poly.coef) for _, poly in self.expressions.values())
        self.coefficients = np.zeros((len(self.scalar), width))
        self.indices = np.zeros(len(self.scalar), dtype=int)
        for row, joint in enumerate(self.scalar):
            root, poly = self.expressions[joint]
            self.coefficients[row, :len(poly.coef)] = poly.coef
            self.indices[row] = self.root_index[root] if root is not None else 0
        self.powers = np.arange(width)
        self.apply(self.reference_independent, self.reference)
        self.check(self.reference)

    def apply(self, independent, qpos):
        values = independent[self.indices]
        qpos[self.addresses] = np.sum(self.coefficients * values[:, None] ** self.powers[None, :], axis=1)
        return qpos

    def check(self, qpos, tolerance=1e-8):
        violation = equality = 0.
        for joint in self.scalar:
            if self.model.jnt_limited[joint]:
                value = qpos[self.model.jnt_qposadr[joint]]
                low, high = self.model.jnt_range[joint]
                violation = max(violation, low - value, value - high)
        for child, (parent, coefficients) in self.dependencies.items():
            ref = self.model.qpos0[self.model.jnt_qposadr[child]]
            x = 0. if parent < 0 else qpos[self.model.jnt_qposadr[parent]] - self.model.qpos0[self.model.jnt_qposadr[parent]]
            expected = ref + np.polynomial.polynomial.polyval(x, coefficients)
            equality = max(equality, abs(qpos[self.model.jnt_qposadr[child]] - expected))
        if max(violation, equality) > tolerance:
            raise ValueError(f'Infeasible pose: range violation={violation}, coupling error={equality}')
        return {'max_range_violation': float(violation), 'max_joint_coupling_error': float(equality)}
