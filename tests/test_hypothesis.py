# -*- coding: utf-8 -*-
# Copyright 2018 Peter C Kroon

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from hypothesis import strategies as st
from hypothesis.stateful import (RuleBasedStateMachine, rule, invariant,
                                 initialize, run_state_machine_as_test)
from hypothesis import example, note, settings
from hypothesis_networkx import graph_builder

from pysmiles import read_smiles
from pysmiles import write_smiles
from pysmiles.smiles_helper import (add_explicit_hydrogens,
    remove_explicit_hydrogens, mark_aromatic_atoms, mark_aromatic_edges,
    fill_valence, correct_aromatic_rings, increment_bond_orders, )
from pysmiles.testhelper import GraphTest


def no_none_value(mapping):
    return {k: v for k, v in mapping.items() if v is not None}


def no_invalid_values(mapping):
    invalids = {'class': 0, 'element': '*'}
    for k, v in invalids.items():
        if mapping.get(k) == v:
            del mapping[k]
    return mapping


isotope = st.one_of(st.none(), st.integers(min_value=1))
element = st.sampled_from('C N O S P *'.split())
hcount = st.integers(min_value=0, max_value=9)
charge = st.integers(min_value=-99, max_value=99)
class_ = st.one_of(st.none(), st.integers(min_value=0))

node_data = st.fixed_dictionaries({'isotope': isotope,
                                   'hcount': hcount,
                                   'element': element,
                                   'charge': charge,
                                   'class': class_}).map(no_invalid_values).map(no_none_value)
order = st.sampled_from([1, 2, 3, 0, 4, 1.5])
edge_data = st.fixed_dictionaries({'order': order})

arom_triangle = read_smiles('[*]1[*][*]1')
for edge in arom_triangle.edges:
    arom_triangle.edges[edge]['order'] = 1


class SMILESTests(RuleBasedStateMachine):
    @initialize(mol=graph_builder(node_data=node_data, edge_data=edge_data,
                                  min_nodes=1))
    @example(mol=arom_triangle)
    def setup(self, mol):
        self.mol = mol
        self.explicit_h = False
        note(self.mol.nodes(data=True))
        note(self.mol.edges(data=True))

    @rule()
    def add_explicit_hydrogens(self):
        self.explicit_h = True
        add_explicit_hydrogens(self.mol)

    @rule()
    def remove_explicit_hydrogens(self):
        self.explicit_h = False
        remove_explicit_hydrogens(self.mol)

    @rule()
    def correct_aromatic_rings(self):
        correct_aromatic_rings(self.mol)
        if self.explicit_h:
            # Correct aromatic rings calls fill valence, see below.
            add_explicit_hydrogens(self.mol)

    @rule()
    def fill_valence(self):
        fill_valence(self.mol)
        if self.explicit_h:
            # Fill valence adds implicit hydrogens, so make them explicit again
            add_explicit_hydrogens(self.mol)

    @rule()
    def increment_bond_orders(self):
        increment_bond_orders(self.mol)

    @invariant()
    def write_read_cycle(self):
        if not hasattr(self, 'mol'):
            return
        smiles = write_smiles(self.mol)
        note(self.mol.nodes(data=True))
        note(self.mol.edges(data=True))
        note([smiles, self.explicit_h])
        found = read_smiles(smiles, explicit_hydrogen=self.explicit_h)
        note(found.nodes(data=True))
        note(found.edges(data=True))
        self.assertEqualGraphs(self.mol, found)


class Tester(GraphTest):
    def _make_state_machine(self):
        state_machine = SMILESTests()
        state_machine.assertEqualGraphs = self.assertEqualGraphs
        return state_machine

    def test_hypo(self):
        run_state_machine_as_test(self._make_state_machine, settings(max_examples=250))
