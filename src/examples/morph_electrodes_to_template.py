import os.path as op
import numpy as np
from collections import defaultdict
import nibabel as nib
import glob
# from scipy.spatial.distance import cdist
from src.utils import trans_utils as tut
import csv
import shutil
import warnings
import os
from src.utils import utils
from src.utils import preproc_utils as pu
from src.utils import freesurfer_utils as fu

SUBJECTS_DIR, MMVT_DIR, FREESURFER_HOME = pu.get_links()

os.environ['SUBJECTS_DIR'] = SUBJECTS_DIR

mri_robust_register = 'mri_robust_register --mov {subjects_dir}/{subject_from}/mri/T1.mgz --dst {subjects_dir}/{subject_to}/mri/T1.mgz --lta {subjects_dir}/{subject_from}/mri/{lta_name}.lta --satit --mapmov {subjects_dir}/{subject_from}/mri/T1_to_{subject_to}.mgz --cost nmi'
mri_cvs_register = 'mri_cvs_register --mov {subject_from} --template {subject_to} ' + \
                   '--outdir {subjects_dir}/{subject_from}/mri_cvs_register_to_{subject_to} --nocleanup --openmp {openmp}' # --step3'
mri_cvs_register_mni = 'mri_cvs_register --mov {subject_from} --mni ' + \
                   '--outdir {subjects_dir}/{subject_from}/mri_cvs_register_to_mni --nocleanup --openmp {openmp}' # --step3'
mri_vol2vol = 'mri_vol2vol --mov {subjects_dir}/{subject}/mri/T1.mgz ' + \
    '--o {subjects_dir}/{subject}/mri/T1_to_colin_csv_register.mgz --m3z ' + \
    '{subjects_dir}/{subject}/mri_cvs_register_to_colin27/final_CVSmorph_tocolin27.m3z ' + \
    '--noDefM3zPath --no-save-reg --targ {subjects_dir}/colin27/mri/T1.mgz'
mri_elcs2elcs = 'mri_vol2vol --mov {subjects_dir}/{subject}/electrodes/{elcs_file_name} ' + \
    '--o {subjects_dir}/{subject}/electrodes/{output_name}_to_colin27.nii.gz --m3z ' + \
    '{subjects_dir}/{subject}/mri_cvs_register_to_colin27/final_CVSmorph_tocolin27.m3z ' + \
    '--noDefM3zPath --no-save-reg --targ {subjects_dir}/colin27/mri/T1.mgz'
apply_morph = 'applyMorph --template {subjects_dir}/{subject_to}/mri/orig.mgz ' \
             '--transform {subjects_dir}/{subject_from}/mri_cvs_register_to_{subject_to}/' + \
             'combined_to{subject_to}_elreg_afteraseg-norm.tm3d ' + \
             'point_list {subjects_dir}/{subject_from}/electrodes/{electrodes_to_morph_file_name}.txt ' + \
             '{mmvt_dir}/{subject_from}/electrodes/{morphed_electrodes_file_name}.txt a'
apply_morph_mni = 'applyMorph --template {subjects_dir}/{subject_to}/mri/orig.mgz ' \
             '--transform {subjects_dir}/{subject_from}/mri_cvs_register_to_mni/' + \
             'combined_tocvs_avg35_inMNI152_elreg_afteraseg-norm.tm3d ' + \
             'point_list {subjects_dir}/{subject_from}/electrodes/{electrodes_to_morph_file_name}.txt ' + \
             '{mmvt_dir}/{subject_from}/electrodes/{morphed_electrodes_file_name}.txt a'


# def robust_register_to_template(subjects, template_system, subjects_dir, vox2vox=False, print_only=False):
#     subject_to = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
#     for subject_from in subjects:
#         cmd = mri_robust_register
#         lta_name = 't1_to_{}'.format(subject_to)
#         if vox2vox:
#             cmd += ' --vox2vox'
#             lta_name += '_vox2vox'
#         rs = utils.partial_run_script(locals(), print_only=print_only)
#         rs(cmd)


def cvs_register_to_template(electrodes, template_system, subjects_dir, overwrite=False, print_only=False, n_jobs=1,
                             openmp=8):
    subject_to = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    if subject_to == 'fsaverage':
        output_fname = op.join(subjects_dir, '{subject}', 'mri_cvs_register_to_mni',
                               'combined_tocvs_avg35_inMNI152_elreg_afteraseg-norm.tm3d')
    else:
        output_fname = op.join(subjects_dir, '{subject}', 'mri_cvs_register_to_{}'.format(subject_to),
                               'combined_to{}_elreg_afteraseg-norm.tm3d'.format(subject_to))
    subjects = list(electrodes.keys())
    for subject in subjects:
        if op.isfile(output_fname.format(subject=subject)):
            print('{} was already morphed to {}'.format(subject, subject_to))
    no_morph_subjects = []
    for subject in subjects:
        if not op.isfile(output_fname.format(subject=subject)):
            print('{} has to be morphed to {}'.format(subject, subject_to))
            no_morph_subjects.append(subject)
    print('Need to morph {}/{} subjecs'.format(len(no_morph_subjects), len(subjects)))
    subjects = [s for s in subjects if s != subject_to and (overwrite or not op.isfile(output_fname.format(subject=s)))]
    if len(subjects) == 0:
        return
    print('subject to morph: ')
    print(subjects)

    indices = np.array_split(np.arange(len(subjects)), n_jobs)
    chunks = [([subjects[ind] for ind in chunk_indices], subject_to, subjects_dir, overwrite, print_only, openmp)
              for chunk_indices in indices]
    utils.run_parallel(_mri_cvs_register_parallel, chunks, n_jobs)
    return subjects


def _mri_cvs_register_parallel(p):
    subjects, subject_to, subjects_dir, overwrite, print_only, openmp = p
    for subject_from in subjects:
        print('********************* {} ***********************'.format(subject_from))
        # output_fname = op.join(SUBJECTS_DIR, subject_from, 'mri_cvs_register_to_colin27', 'combined_tocolin27_elreg_afteraseg-norm.tm3d')
        # if op.isfile(output_fname) and not overwrite:
        #     print('Already done for {}'.format(subject_from))
        #     continue
        # else:
        #     print('Running mri_cvs_register for {}'.format(subject_from))
        if overwrite and not print_only:
            utils.delete_folder_files(op.join(subjects_dir, subject_from, 'mri_cvs_register_to_{}'.format(subject_to)))
        rs = utils.partial_run_script(locals(), print_only=print_only)
        if subject_to == 'fsaverage':
            rs(mri_cvs_register_mni)
        else:
            rs(mri_cvs_register)


def morph_electrodes(electrodes, template_system, subjects_dir, mmvt_dir, overwrite=False, print_only=False, n_jobs=4):
    subject_to = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    output_fname = op.join(mmvt_dir, '{subject}', 'electrodes', 'electrodes_morph_to_{}.txt'.format(subject_to))
    subjects = [s for s in list(electrodes.keys()) if overwrite or not op.isfile(output_fname.format(subject=s))]
    if len(subjects) > 0:
        indices = np.array_split(np.arange(len(subjects)), n_jobs)
        chunks = [([subjects[ind] for ind in chunk_indices], subject_to, subjects_dir, mmvt_dir, output_fname, overwrite, print_only)
                  for chunk_indices in indices]
        utils.run_parallel(_morph_electrodes_parallel, chunks, n_jobs)
    bad_subjects, good_subjects = [], []
    for subject_from in list(electrodes.keys()):
        ret = op.isfile(output_fname.format(subject=subject_from))
        if not ret:
            bad_subjects.append(subject_from)
        else:
            good_subjects.append(subject_from)
    print('morph_electrodes:')
    print('good subjects: {}'.format(good_subjects))
    print('bad subjects: {}'.format(bad_subjects))
    print('{}/{} good subjects'.format(len(good_subjects), len(list(electrodes.keys()))))


def _morph_electrodes_parallel(p):
    subjects, subject_to, subjects_dir, mmvt_dir, output_fname, overwrite, print_only = p
    bad_subjects, good_subjects = [], []
    for subject_from in subjects:
        electrodes_to_morph_file_name = 'electrodes_to_morph'
        morphed_electrodes_file_name = 'electrodes_morph_to_{}'.format(subject_to)
        output_fname = op.join(mmvt_dir, subject_from, 'electrodes', '{}.txt'.format(morphed_electrodes_file_name))
        if op.isfile(output_fname) and not overwrite:
            print('{} electrode were already morphed to {}'.format(subject_from, subject_to))
            continue
        if subject_to == 'fsaverage':
            subject_to = 'cvs_avg35_inMNI152'
        rs = utils.partial_run_script(locals(), print_only=print_only)
        if subject_to == 'cvs_avg35_inMNI152':
            rs(apply_morph_mni)
        else:
            rs(apply_morph)
        if op.isfile(output_fname):
            print('{}: electrodes file was morphed successfuly! -> {}'.format(subject_from, output_fname))
        else:
            print('{}: Couldn\'t morph the electrodes file!'.format(subject_from))


def read_morphed_electrodes(electrodes, template_system, subjects_dir, mmvt_dir, overwrite=False,
                            subjects_electrodes={}, convert_to_bipolar=False):
    subject_to = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    fol = utils.make_dir(op.join(mmvt_dir, subject_to, 'electrodes'))
    output_fname = op.join(fol, 'template_electrodes.pkl')
    if op.isfile(output_fname) and not overwrite:
        print('{} already exist!'.format(output_fname))
        return
    subject_to_mri = subject_to #'cvs_avg35_inMNI152' if subject_to == 'fsaverage' else subject_to
    t1_header = nib.load(op.join(subjects_dir, subject_to_mri, 'mri', 'T1.mgz')).header
    brain_mask_fname = op.join(subjects_dir, subject_to_mri, 'mri', 'brainmask.mgz')
    brain_mask = nib.load(brain_mask_fname).get_data() if op.isfile(brain_mask_fname) else None
    trans = t1_header.get_vox2ras_tkr()
    template_electrodes = defaultdict(list)
    bad_subjects, good_subjects = [], []
    for subject in electrodes.keys():
        if subject == subject_to:
            continue
        if len(subjects_electrodes) != 0 and subject not in subjects_electrodes:
            continue
        subject_electrodes = trans_morphed_electrodes_to_tkreg(
            subject, subject_to, electrodes, trans, brain_mask, subjects_electrodes)
        if subject_electrodes is None or len(subject_electrodes) == 0:
            bad_subjects.append(subject)
        else:
            template_electrodes[subject] = subject_electrodes
            good_subjects.append(subject)
    if convert_to_bipolar:
        bipolar_template_electrodes = defaultdict(list)
        for subject, elcs_tups in template_electrodes.items():
            pairs = utils.pair_list(elcs_tups)
            for pair in pairs:
                # todo: check that the pair is actually two nei electrodes
                new_bipolar_pos = np.mean([pair[0][1], pair[1][1]], axis=0)
                group1, num1 = utils.elec_group_number('_'.join(pair[0][0].split('_')[1:]), False, False)
                group2, num2 = utils.elec_group_number('_'.join(pair[1][0].split('_')[1:]), False, False)
                if group1 != group2 or abs(int(num1)-int(num2)) != 1:
                    print('Wrong pair! {} {} {}'.format(group1, num1, num2))
                else:
                    num1, num2 = (num1, num2) if int(num2) > int(num1) else (num2, num1)
                    bipolar_template_electrodes[subject].append(
                        ('{}_{}{}-{}'.format(subject, group1, num1, num2), new_bipolar_pos))

    utils.save(template_electrodes, output_fname)
    print('read_morphed_electrodes: {}'.format(op.isfile(output_fname)))
    print('{}/{} good subjects'.format(len(good_subjects), len(electrodes)))
    print('good subjects: {}'.format(good_subjects))
    print('bad subjects: {}'.format(bad_subjects))
    return bipolar_template_electrodes if convert_to_bipolar else template_electrodes


def trans_morphed_electrodes_to_tkreg(subject, subject_to, electrodes, trans, brain_mask, subjects_electrodes=None):
    template_electrodes = []
    morphed_electrodes_file_name = 'electrodes_morph_to_{}.txt'.format(subject_to)
    input_fname = op.join(MMVT_DIR, subject, 'electrodes', morphed_electrodes_file_name)
    if not op.isfile(input_fname):
        print('read_morphed_electrodes: Can\'t find {}!'.format(input_fname))
        return None
    print('Reading {} ({})'.format(input_fname, utils.file_modification_time(input_fname)))
    voxels = np.genfromtxt(input_fname, dtype=np.float, delimiter=' ')
    electrodes_names = [elc_name for (elc_name, _) in electrodes[subject]]
    if subject_to == 'fsaverage':
        voxels = tut.mni152_mni305(voxels)
    #check_if_electrodes_inside_the_brain(subject, voxels, electrodes_names, brain_mask)
    tkregs = apply_trans(trans, voxels)
    write_morphed_electrodes_vox_into_csv(subject, subject_to, tkregs, electrodes_names)
    if subjects_electrodes is not None and subject in subjects_electrodes:
        elecs = [elc_name for elc_name, _ in electrodes[subject] if elc_name in subjects_electrodes[subject]]
        if len(elecs) == 0:
            print('No electrodes for {}! ({})'.format(subject, subjects_electrodes[subject]))
    for tkreg, vox, (elc_name, _) in zip(tkregs, voxels, electrodes[subject]):
        # if subjects_electrodes is not None and elc_name in subjects_electrodes[subject]:
        try:
            vox = np.rint(vox).astype(int)
            if brain_mask[vox[0], vox[1], vox[2]] == 0:
                print('{}: {} is outside the brain!'.format(subject, elc_name))
            template_electrodes.append(('{}_{}'.format(subject, elc_name), tkreg))
        except:
            print('Error with {}, {}, voxels={}'.format(subject, elc_name, vox))

    return template_electrodes


def check_if_electrodes_inside_the_brain(subject, voxels, electrodes_names, brain_mask=None):
    if brain_mask is not None:
        for vox, elc_name in zip(voxels, electrodes_names):
            vox = np.rint(vox).astype(int)
            try:
                mask = brain_mask[vox[0], vox[1], vox[2]]
                if mask == 0:
                    print('{}: {} is outside the brain!'.format(subject, elc_name))
            except:
                print('Error with {}, {}, voxels={}'.format(subject, elc_name, vox))


def write_morphed_electrodes_vox_into_csv(subject, subject_to, voxels, electrodes_names):
    fol = utils.make_dir(op.join(MMVT_DIR, subject_to, 'electrodes'))
    csv_fname = op.join(fol, '{}_morphed_to_{}_RAS.csv'.format(subject, subject_to))
    print('Writing csv file to {}'.format(csv_fname))
    with open(csv_fname, 'w') as csv_file:
        wr = csv.writer(csv_file, quoting=csv.QUOTE_NONE)
        wr.writerow(['Electrode Name','R','A','S'])
        for elc_name, elc_coords in zip(electrodes_names, voxels):
            wr.writerow([elc_name, *elc_coords.squeeze()])


def apply_trans(trans, points):
    if isinstance(points, list):
        points = np.array(points)
    ndim = points.ndim
    if ndim == 1:
        points = [points]
    points = np.hstack((points, np.ones((len(points), 1))))
    points = np.dot(trans, points.T).T
    points = points[:, :3]
    if ndim == 1:
        points = points[0]
    return points


def lta_transfer_ras2ras(subject, coords, return_trans=False):
    lta_fname = op.join(SUBJECTS_DIR, subject, 'mri', 't1_to_{}.lta'.format(template_system))
    if not op.isfile(lta_fname):
        return None
    lta = fu.read_lta_file(lta_fname)
    lta[np.isclose(lta, np.zeros(lta.shape))] = 0
    subject_header = nib.load(op.join(SUBJECTS_DIR, subject, 'mri', 'T1.mgz')).get_header()
    template_header = nib.load(op.join(SUBJECTS_DIR, template_system, 'mri', 'T1.mgz')).get_header()
    vox = apply_trans(np.linalg.inv(subject_header.get_vox2ras_tkr()), coords)
    ras = apply_trans(subject_header.get_vox2ras(), vox)
    template_ras = apply_trans(lta, ras)
    template_vox = apply_trans(template_header.get_ras2vox(), template_ras)
    template_cords = apply_trans(template_header.get_vox2ras_tkr(), template_vox)
    if return_trans:
        return template_cords, lta
    else:
        return template_cords


def lta_transfer_vox2vox(subject, coords):
    lta_fname = op.join(SUBJECTS_DIR, subject, 'mri', 't1_to_{}_vox2vox.lta'.format(template_system))
    if not op.isfile(lta_fname):
        return None
    lta = fu.read_lta_file(lta_fname)
    subject_header = nib.load(op.join(SUBJECTS_DIR, subject, 'mri', 'T1.mgz')).get_header()
    template_header = nib.load(op.join(SUBJECTS_DIR, template_system, 'mri', 'T1.mgz')).get_header()
    vox = apply_trans(np.linalg.inv(subject_header.get_vox2ras_tkr()), coords)
    template_vox = apply_trans(lta, vox)
    template_cords = apply_trans(template_header.get_vox2ras_tkr(), template_vox)
    return template_cords


def transfer_electrodes_to_template_system(electrodes, template_system, use_mri_robust_lta=False, vox2vox=False):
    import time
    teamplte_electrodes = defaultdict(list)
    for subject in electrodes.keys():
        # if subject != 'mg101':
        #     continue
        now, N = time.time(), len(electrodes[subject])
        for run, (elc_name, coords) in enumerate(electrodes[subject]):
            utils.time_to_go(now, run, N, runs_num_to_print=5)
            if use_mri_robust_lta:
                if vox2vox:
                    template_cords = lta_transfer_vox2vox(subject, coords)
                else:
                    template_cords = lta_transfer_ras2ras(subject, coords)
            else:
                if template_system == 'ras':
                    template_cords = fu.transform_subject_to_ras_coordinates(subject, coords, SUBJECTS_DIR)
                elif template_system == 'mni':
                    template_cords = fu.transform_subject_to_mni_coordinates(subject, coords, SUBJECTS_DIR)
                else:
                    template_cords = fu.transform_subject_to_subject_coordinates(
                        subject, template_system, coords, SUBJECTS_DIR)
            if template_cords is not None:
                teamplte_electrodes[subject].append((elc_name, template_cords))
    return teamplte_electrodes


def read_csv_file(csv_fname, save_as_bipolar):
    csv_lines = np.genfromtxt(csv_fname,  dtype=str, delimiter=',', skip_header=1)
    electrodes = defaultdict(list)
    for line in csv_lines:
        subject = line[0].lower()
        elecs_names = [e.strip() for e in line[1:3].tolist()]
        elecs_groups = [utils.elec_group(e) for e in elecs_names]
        if elecs_groups[0] == elecs_groups[1]:
            elec_name = '{}-{}'.format(elecs_names[1], elecs_names[0])
        else:
            print('The electrodes has different groups! {}, {}'.format(elecs_groups[0], elecs_groups[1]))
            continue
        coords1 = line[3:6].astype(np.float)
        coords2 = line[6:9].astype(np.float)
        if save_as_bipolar:
            coords = (coords1 + (coords2 - coords1) / 2)
            electrodes[subject].append((elec_name, coords))
        else:
            electrodes[subject].append((elecs_names[0], coords1))
            electrodes[subject].append((elecs_names[1], coords2))
    return electrodes


def read_all_electrodes(subjects, bipolar):
    from src.preproc import electrodes as elc_pre
    electrodes = defaultdict(list)
    bads, goods = [], []
    for subject in subjects:
        names, pos = elc_pre.read_electrodes_file(subject, bipolar)
        if len(names) == 0:
            bads.append(subject)
        else:
            goods.append(subject)
        for elec_name, coords in zip(names, pos):
            electrodes[subject].append((elec_name, coords))
    print('read_all_eletrodes:')
    print('bads: {}'.format(bads))
    print('goods: {}'.format(goods))
    return electrodes


def save_template_electrodes_to_template(template_electrodes, bipolar, mmvt_dir, template_system='mni', prefix='', postfix=''):
    output_fname = '{}electrodes{}_positions.npz'.format(prefix, '_bipolar' if bipolar else '', postfix)
    template = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    if template_electrodes is None:
        input_fname = op.join(mmvt_dir, template, 'electrodes', 'template_electrodes.pkl')
        print('Reading {} ({})'.format(input_fname, utils.file_modification_time(input_fname)))
        template_electrodes = utils.load(input_fname)
    fol = utils.make_dir(op.join(MMVT_DIR, template, 'electrodes'))
    output_fname = op.join(fol, output_fname)
    elecs_coordinates = np.array(utils.flat_list_of_lists(
        [[e[1] for e in template_electrodes[subject]] for subject in template_electrodes.keys()]))
    elecs_names = utils.flat_list_of_lists(
        [[e[0] for e in template_electrodes[subject]] for subject in template_electrodes.keys()])
    np.savez(output_fname, pos=elecs_coordinates, names=elecs_names, pos_org=[])
    print('Electrodes were saved to {}'.format(output_fname))


def export_into_csv(template_system, mmvt_dir, bipolar=False, prefix='', input_fname=''):
    template = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    if input_fname == '':
        input_name = '{}electrodes{}_positions.npz'.format(prefix, '_bipolar' if bipolar else '')
        input_fname = op.join(mmvt_dir, template, 'electrodes', input_name)
    electrodes_dict = utils.Bag(np.load(input_fname))
    fol = utils.make_dir(op.join(MMVT_DIR, template, 'electrodes'))
    csv_fname = op.join(fol, '{}{}_{}RAS.csv'.format(prefix, template, 'bipolar_' if bipolar else ''))
    print('Writing csv file to {}'.format(csv_fname))
    with open(csv_fname, 'w') as csv_file:
        wr = csv.writer(csv_file, quoting=csv.QUOTE_NONE)
        wr.writerow(['Electrode Name','R','A','S'])
        for elc_name, elc_coords in zip(electrodes_dict.names, electrodes_dict.pos):
            wr.writerow([elc_name, *['{:.2f}'.format(x) for x in elc_coords.squeeze()]])
    fol = utils.make_dir(op.join(MMVT_DIR, template, 'electrodes'))
    csv_fname2 = op.join(fol, utils.namebase_with_ext(csv_fname))
    if csv_fname != csv_fname2:
        utils.copy_file(csv_fname, csv_fname2)
    print('export_into_csv: {}'.format(op.isfile(csv_fname) and op.isfile(csv_fname2)))
    return csv_fname


# def compare_electrodes_labeling(electrodes, template_system, atlas='aparc.DKTatlas'):
#     template = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
#     template_elab_files = glob.glob(op.join(
#         MMVT_DIR, template, 'electrodes', '{}_{}_electrodes_cigar_r_3_l_4.pkl'.format(template, atlas)))
#     if len(template_elab_files) == 0:
#         print('No electrodes labeling file for {}!'.format(template))
#         return
#     elab_template = utils.load(template_elab_files[0])
#     errors = ''
#     for subject in electrodes.keys():
#         elab_files = glob.glob(op.join(
#             MMVT_DIR, subject, 'electrodes', '{}_{}_electrodes_cigar_r_3_l_4.pkl'.format(subject, atlas)))
#         if len(elab_files) == 0:
#             print('No electrodes labeling file for {}!'.format(subject))
#             continue
#         electrodes_names = [e[0] for e in electrodes[subject]]
#         elab = utils.load(elab_files[0])
#         elab = [e for e in elab if e['name'] in electrodes_names]
#         for elc in electrodes_names:
#             no_errors = True
#             elc_labeling = [e for e in elab if e['name'] == elc][0]
#             elc_labeling_template = [e for e in elab_template if e['name'] == '{}_{}'.format(subject, elc)][0]
#             for roi, prob in zip(elc_labeling['cortical_rois'], elc_labeling['cortical_probs']):
#                 no_err, err = compare_rois_and_probs(
#                     subject, template, elc, roi, prob, elc_labeling['cortical_rois'],
#                     elc_labeling_template['cortical_rois'], elc_labeling_template['cortical_probs'])
#                 no_errors = no_errors and no_err
#                 if err != '':
#                     errors += err + '\n'
#             for roi, prob in zip(elc_labeling['subcortical_rois'], elc_labeling['subcortical_probs']):
#                 no_err, err = compare_rois_and_probs(
#                     subject, template, elc, roi, prob, elc_labeling['subcortical_rois'],
#                     elc_labeling_template['subcortical_rois'], elc_labeling_template['subcortical_probs'])
#                 no_errors = no_errors and no_err
#                 if err != '':
#                     errors += err + '\n'
#             if no_errors:
#                 print('{},{},Good!'.format(subject, elc))
#                 errors += '{},{},Good!\n'.format(subject, elc)
#     with open(op.join(MMVT_DIR, template, 'electrodes', 'trans_errors.txt'), "w") as text_file:
#         print(errors, file=text_file)
#     # print(errors)


# def compare_rois_and_probs(subject, template, elc, roi, prob, elc_labeling_rois, elc_labeling_template_rois,
#                            elc_labeling_template_rois_probs):
#     no_errors = True
#     err = ''
#     if roi not in elc_labeling_template_rois:
#         if prob > 0.05:
#             err = f'{subject},{elc},{roi} ({prob}) not in {template}'
#             print(err)
#             no_errors = False
#     else:
#         roi_ind = elc_labeling_template_rois.index(roi)
#         template_roi_prob = elc_labeling_template_rois_probs[roi_ind]
#         if abs(prob - template_roi_prob) > 0.05:
#             err = f'{subject},{elc},{roi} prob ({prob} != {template} prob ({template_roi_prob})'
#             print(err)
#             no_errors = False
#     for roi, prob in zip(elc_labeling_template_rois, elc_labeling_template_rois_probs):
#         if roi not in elc_labeling_rois and prob > 0.05:
#             err = f'{subject},{elc},{roi} ({prob}) only in {template}'
#             print(err)
#             no_errors = False
#     return no_errors, err


def prepare_files(subjects, template_system):
    template = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    # mri_cvs_check --mov {subject} --template {template}
    necessary_files = {'surf': ['lh.inflated', 'rh.inflated', 'lh.pial', 'rh.pial', 'rh.white', 'lh.white',
                                'lh.smoothwm', 'rh.smoothwm', 'rh.sulc', 'lh.sulc', 'lh.sphere', 'rh.sphere',
                                'lh.inflated.K', 'rh.inflated.K', 'lh.inflated.H', 'rh.inflated.H'],
                       'label': ['lh.aparc.annot', 'rh.aparc.annot']}
    if template != 'fsaverage':
        subjects = list(subjects) + [template]
    martinos_subjects = {'mg96':'ep007', 'mg78': 'ep001', 'ep001': 'ep001'}
    goods, bads = [], []
    for subject in subjects:
        files_exist = utils.check_if_all_necessary_files_exist(
            subject, necessary_files, op.join(SUBJECTS_DIR, subject), trace=True)
        if files_exist:
            goods.append(subject)
            continue
        darpa_subject = subject[:2].upper() + subject[2:]
        fols = glob.glob(op.join(
            '/homes/5/npeled/space1/Angelique/recon-alls/{}/'.format(darpa_subject), '**', '{}_SurferOutput'.format(darpa_subject)),
            recursive=True)
        remote_subject_dir = fols[0] if len(fols) == 1 else ''
        files_exist = get_subject_files(subject, necessary_files, remote_subject_dir)
        if not files_exist:
            remote_subject_dir = op.join('/space/huygens/1/users/kara', '{}_SurferOutput'.format(darpa_subject))
            files_exist = get_subject_files(subject, necessary_files, remote_subject_dir)
        if not files_exist and subject in martinos_subjects.keys():
            remote_subject_dir = op.join(
                '/autofs/space/lilli_001/users/DARPA-Recons/', martinos_subjects[subject])
            files_exist = get_subject_files(subject, necessary_files, remote_subject_dir)
        if files_exist:
            goods.append(subject)
        else:
            bads.append(subject)
    print('goods: {}'.format(goods))
    print('bads: {}'.format(bads))
    return goods, bads


def get_subject_files(subject, necessary_files, remote_subject_dir):
    if not op.isdir(remote_subject_dir):
        return False
    return utils.prepare_subject_folder(
        necessary_files, subject, remote_subject_dir, SUBJECTS_DIR, print_traceback=False)


def create_electrodes_files(electrodes, subjects_dir, overwrite=False):
    for subject in electrodes.keys():
        fol = utils.make_dir(op.join(SUBJECTS_DIR, subject, 'electrodes'))
        electrodes_to_morph_file_name = 'electrodes_to_morph.txt'
        csv_fname = op.join(fol, electrodes_to_morph_file_name)
        if op.isfile(csv_fname) and not overwrite:
            continue
        t1_fname = op.join(subjects_dir, subject, 'mri', 'T1.mgz')
        if not op.isfile(t1_fname):
            print('Can\'t find T1.mgz for {}!'.format(subject))
            continue
        t1_header = nib.load(t1_fname).header
        brain_mask_fname = op.join(subjects_dir, subject, 'mri', 'brainmask.mgz')
        if op.isfile(brain_mask_fname):
            brain_mask = nib.load(brain_mask_fname).get_data()
        trans = np.linalg.inv(t1_header.get_vox2ras_tkr())
        print('create_electrodes_files: Writing to {}'.format(csv_fname))
        with open(csv_fname, 'w') as csv_file:
            wr = csv.writer(csv_file, quoting=csv.QUOTE_NONE, delimiter=' ')
            for elc_name, coords in electrodes[subject]:
                vox = np.rint(apply_trans(trans, coords)).astype(int)
                if op.isfile(brain_mask_fname):
                    mask = brain_mask[vox[0], vox[1], vox[2]]
                    if mask == 0:
                        print('{}: {} is outside the brain!'.format(subject, elc_name))
                # wr.writerow([*['{:.2f}'.format(x) for x in vox]])
                wr.writerow(vox)


def create_mmvt_coloring_file(template_system, template_electrodes, electodes_colors={}):
    template = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    fol = utils.make_dir(op.join(MMVT_DIR, template, 'coloring'))
    csv_fname = op.join(fol, 'morphed_electrodes.csv')
    print('Writing csv file to {}'.format(csv_fname))
    subjects = list(template_electrodes.keys())
    if len(electodes_colors) != 0:
        unique_colors = np.unique(utils.flat_list(([[k[1] for k in elecs] for elecs in electodes_colors.values()])))
        colors = utils.get_distinct_colors(len(unique_colors))
        min_elc_ind_val = min(unique_colors)
    else:
        colors = utils.get_distinct_colors(len(subjects))
    with open(csv_fname, 'w') as csv_file:
        wr = csv.writer(csv_file, quoting=csv.QUOTE_NONE)
        for subject_ind, subject in enumerate(subjects):
            # for elc_name, _ in template_electrodes[subject]:
            for elc_name in template_electrodes[subject]:
                if len(electodes_colors) != 0:
                    real_elc_name = '_'.join(elc_name.split('_')[1:])
                    elec_id = [tup for tup in electodes_colors[subject] if tup[0] == real_elc_name][0][1]
                    color = colors[elec_id - min_elc_ind_val]
                else:
                    color = colors[subject_ind]
                wr.writerow([elc_name, *color])
    print('Writing colors for {} electrodes, {} subjects'.format(
        sum([len(template_electrodes[s]) for s in subjects]), len(subjects)))


def get_output_using_sftp(subjects, subject_to):
    sftp_domain = 'door.nmr.mgh.harvard.edu'
    sftp_username = 'npeled'
    remote_subject_dir = '/space/thibault/1/users/npeled/subjects/{subject}'
    necessary_files = {'mri_cvs_register_to_{}'.format(subject_to):
                           ['combined_to{}_elreg_afteraseg-norm.tm3d'.format(subject_to)]}
    password = ''
    for subject in subjects:
        print('Getting tm3d file for {}'.format(subject))
        utils.make_dir(op.join(SUBJECTS_DIR, subject, 'electrodes'))
        ret, password_temp = utils.prepare_subject_folder(
            necessary_files, subject, remote_subject_dir.format(subject=subject.lower()), SUBJECTS_DIR,
            True, sftp_username, sftp_domain, sftp_password=password)
        if not ret:
            print('Error in copying the file!')
        if password_temp != '':
            password = password_temp


def prepare_files_for_subjects(subjects, remote_subject_templates, sftp=False,  sftp_username='', sftp_domain='',
                               overwrite=False):
    necessary_files = {'surf': ['lh.inflated', 'rh.inflated', 'lh.pial', 'rh.pial', 'rh.white', 'lh.white',
                                'lh.smoothwm', 'rh.smoothwm', 'rh.sulc', 'lh.sulc', 'lh.sphere', 'rh.sphere',
                                'lh.inflated.K', 'rh.inflated.K', 'lh.inflated.H', 'rh.inflated.H'],
                       'mri': ['aseg.mgz', 'norm.mgz', 'ribbon.mgz', 'T1.mgz', 'orig.mgz', 'brain.mgz'],
                       'label': ['lh.aparc.annot', 'rh.aparc.annot']}

    # subjects = pu.decode_subjects(['MG*'], remote_subject_template)
    good_subjects = []
    for subject in subjects:
        for remote_subject_template in remote_subject_templates:
            remote_subject_template = remote_subject_template.replace('{hosp}', subject[:2])
            remote_subject_dir = utils.build_remote_subject_dir(remote_subject_template, subject)
            all_files_exist, _ = utils.prepare_subject_folder(
                necessary_files, subject, remote_subject_dir, SUBJECTS_DIR, overwrite_files=overwrite,
                sftp=sftp, sftp_username=sftp_username, sftp_domain=sftp_domain, print_missing_files=False)
            if all_files_exist:
                good_subjects.append(subject)
                break
    bad_subjects = list(set(subjects) - set(good_subjects))
    print('prepare_files: {}/{} good subjects'.format(len(good_subjects), len(subjects)))
    print('Good: {}'.format(good_subjects))
    print('Bad: {}'.format(bad_subjects))
    # if len(bad_subjects) > 0:
        # from src.preproc import anatomy as anat
        # for subject in bad_subjects:
        #     args = anat.read_cmd_args(dict(
        #         subject=subject,
        #         remote_subject_dir='/mnt/cashlab/Original Data/MG/{subject}/{subject}_Notes_and_Images/{subject}_SurferOutput',
        #         function='prepare_subject_folder'
        #     ))
        #     args.necessary_files = necessary_files
        #     pu.run_on_subjects(args, anat.main)
    return good_subjects


def get_all_subjects(remote_subject_template):
    subjects = pu.decode_subjects(['MG*'], remote_subject_template)
    return subjects


def main(subjects, template_system, remote_subject_templates=(), bipolar=False, save_as_bipolar=False, overwrite=False,
         prefix='', sftp=False, sftp_username='', sftp_domain='', print_only=False, n_jobs=4):
    good_subjects = prepare_files_for_subjects(
        subjects, remote_subject_templates, sftp, sftp_username, sftp_domain, overwrite=False)
    electrodes = read_all_electrodes(good_subjects, bipolar)
    subjects_to_morph = cvs_register_to_template(
        electrodes, template_system, SUBJECTS_DIR, n_jobs=n_jobs, print_only=print_only, overwrite=overwrite)
    create_electrodes_files(electrodes, SUBJECTS_DIR, overwrite=True)
    morph_electrodes(
        electrodes, template_system, SUBJECTS_DIR, MMVT_DIR, overwrite=overwrite, n_jobs=n_jobs, print_only=print_only)
    read_morphed_electrodes(electrodes, template_system, SUBJECTS_DIR, MMVT_DIR, overwrite=True)
    save_template_electrodes_to_template(None, save_as_bipolar, MMVT_DIR, template_system, prefix)
    export_into_csv(template_system, MMVT_DIR, prefix)
    # create_mmvt_coloring_file(template_system, electrodes)sss



if __name__ == '__main__':
    template_system = 'ras'# ''ras' #'matt_hibert' # 'mni' # hc029
    template = 'fsaverage' if template_system == 'ras' else 'colin27' if template_system == 'mni' else template_system
    bipolar, save_as_bipolar = False, False
    use_apply_morph = True
    prefix, postfix = '', '' # 'stim_'
    overwrite=False
    # remote_subject_template = '/mnt/cashlab/Original Data/MG/{subject}/{subject}_Notes_and_Images/{subject}_SurferOutput'
    remote_subject_template = '/autofs/space/will_002/users/Conte_PET_analyses_10.14.11/DBS_OCD_MRI/{subject}'
    # subjects = set(['MG51b', 'MG72', 'MG73', 'MG83', 'MG76', 'MG84', 'MG84', 'MG85', 'MG86', 'MG86', 'MG87', 'MG87', 'MG90', 'MG91', 'MG91', 'MG92', 'MG93', 'MG94', 'MG95', 'MG96', 'MG96', 'MG96', 'MG98', 'MG100', 'MG103', 'MG104', 'MG105', 'MG105', 'MG106', 'MG106', 'MG106', 'MG106', 'MG107', 'MG108', 'MG108', 'MG109', 'MG109', 'MG110', 'MG111', 'MG112', 'MG112', 'MG114', 'MG114', 'MG115', 'MG116', 'MG118', 'MG120', 'MG120', 'MG121', 'MG122', 'BW36', 'BW37', 'BW38', 'BW39', 'BW40', 'BW40', 'BW40', 'BW40', 'BW42', 'BW43', 'BW44'])
    #subjects = ['MG96', 'MG98', 'MG100', 'MG122', 'MG106', 'BW37', 'BW38', 'BW39', 'BW40'] # bad
    # subjects = ['MG100', 'MG106', 'BW40', 'MG105', 'BW39', 'BW38', 'MG98', 'BW37']
    subjects = ['M1']
    file_missings=[]

    print('{} subject to preproc'.format(len(subjects)))
    remote_subject_template1 = '/mnt/cashlab/Original Data/{hosp}/{subject}/{subject}_Notes_and_Images/{subject}_SurferOutput'
    remote_subject_template2 = '/mnt/cashlab/Original Data/{hosp}/{subject}/{subject}_Notes_and_Images/Recon/{subject}_SurferOutput'
    remote_subject_template3 = '/mnt/cashlab/Original Data/{hosp}/{subject}/{subject}_SurferOutput'
    remote_subject_template4 = '/mnt/cashlab/projects/DARPA/{hosp}/{subject}/{subject}_Notes_and_Images/{subject}_SurferOutput_REDONE'
    remote_subject_template5 = '/usr/local/freesurfer/dev/subjects/{subject}'
    remote_subject_templates = (remote_subject_template1, remote_subject_template2, remote_subject_template3,
                                remote_subject_template4, remote_subject_template5)

    remote_subject_templates = [remote_subject_template]

    import argparse
    from src.utils import args_utils as au
    parser = argparse.ArgumentParser(description='MMVT')
    parser.add_argument('-s', '--subject', help='subject name', required=False, default='', type=au.str_arr_type)
    parser.add_argument('-f', '--function', help='function name', required=False, default='')
    parser.add_argument('--print_only', required=False, default=False, type=au.is_true)
    parser.add_argument('--sftp', required=False, default=False, type=au.is_true)
    parser.add_argument('--sftp_username', help='sftp username', required=False, default='npeled')
    parser.add_argument('--sftp_domain', help='sftp domain', required=False, default='door.nmr.mgh.harvard.edu')
    parser.add_argument('--n_jobs', help='cpu num', required=False, default=1)

    args = utils.Bag(au.parse_parser(parser))
    args.n_jobs = utils.get_n_jobs(args.n_jobs)
    if len(args.subject) == 0:
        args.subject = subjects
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        main(args.subject, template_system, remote_subject_templates, bipolar, save_as_bipolar, overwrite, prefix,
             args.sftp, args.sftp_username, args.sftp_domain, args.print_only, args.n_jobs)
    print('Done!')

    print('finish')