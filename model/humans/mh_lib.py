"""Realistic people via MPFB (MakeHuman for Blender): body, skin, hair, eyes, clothes, rig, pose.

Assets: MakeHuman community asset packs (CC0 / CC-BY), installed in MPFB's user data dir.
"""
import os

import addon_utils
import bpy

addon_utils.enable('io_anim_bvh', default_set=True)
addon_utils.enable('bl_ext.user_default.mpfb', default_set=True)

from bl_ext.user_default.mpfb.services.humanservice import HumanService  # noqa: E402
from bl_ext.user_default.mpfb.services.animationservice import AnimationService  # noqa: E402
from bl_ext.user_default.mpfb.services.assetservice import AssetService  # noqa: E402

DATA = bpy.utils.extension_path_user('bl_ext.user_default.mpfb') + '/data'


def pose_file(name):
    return os.path.join(DATA, 'poses', name, name + '.bvh')


def make_person(name, phenotype, skin, hair='', eyebrows='eyebrow001', clothes=(), rig='default',
                eyes_mat='brown', subdiv=1):
    info = HumanService._create_default_human_info_dict()
    info['name'] = name
    info['phenotype'].update({k: v for k, v in phenotype.items() if k != 'race'})
    if 'race' in phenotype:
        info['phenotype']['race'] = phenotype['race']
    info['rig'] = rig
    info['eyes'] = 'high-poly/high-poly.mhclo'
    info['eyebrows'] = '%s/%s.mhclo' % (eyebrows, eyebrows) if eyebrows else ''
    info['eyelashes'] = 'eyelashes01/eyelashes01.mhclo'
    info['hair'] = '%s/%s.mhclo' % (hair, hair) if hair else ''
    info['clothes'] = ['%s/%s.mhclo' % (c, c) for c in clothes]
    info['skin_mhmat'] = '%s/%s.mhmat' % (skin, skin)
    info['skin_material_type'] = 'ENHANCED_SSS'
    info['eyes_material_type'] = 'MAKESKIN'
    st = HumanService.get_default_deserialization_settings()
    st['subdiv_levels'] = subdiv
    body = HumanService.deserialize_from_dict(info, st)
    rig_ob = body.parent
    return rig_ob, body


def apply_pose(rig_ob, pose_name):
    AnimationService.import_bvh_file_as_pose(rig_ob, pose_file(pose_name))
