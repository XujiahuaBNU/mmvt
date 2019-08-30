import os.path as op
import nibabel as nib
import numpy as np
from collections import defaultdict
from src.utils import utils
from src.utils import preproc_utils as pu
# from src.examples import morph_electrodes_to_template
from src.preproc import anatomy as anat, ela_morph_electrodes

SUBJECTS_DIR, MMVT_DIR, FREESURFER_HOME = pu.get_links()


def read_xls(xls_fname, subject_to='colin27', atlas='aparc.DKTatlas', annotation_template='fsaverage',
             overwrite=False, check_morph_file=False):
    # bipolar = True
    # template_header = nib.load(op.join(SUBJECTS_DIR, subject_to, 'mri', 'T1.mgz')).header
    subjects_electrodes = defaultdict(list)
    # electrodes_colors = defaultdict(list)
    for line in utils.xlsx_reader(xls_fname, skip_rows=1):
        subject, elec1_name, elec2_name, cond, patient_id  = line[:5]
        subject = subject.lower()
        elec1_coo, elec2_coo = line[5:8], line[8:11]
        # elec_group = utils.elec_group(elec1_name, bipolar=False)
        # if check_morph_file:
        #     electrodes_fname = op.join(MMVT_DIR, subject, 'electrodes', 'electrodes_morph_to_{}.txt'.format(subject_to))
        #     if not op.isfile(electrodes_fname):
        #         continue
        # elec_group, num1, num2 = utils.elec_group_number(elec_name, bipolar)
        # if '{}{}-{}'.format(elec_group, num2, num1) != elec_name:
        #     num1, num2 = str(num1).zfill(2), str(num2).zfill(2)
        # if '{}{}-{}'.format(elec_group, num2, num1) != elec_name:
        #     raise Exception('Wrong group or numbers!')
        # for num in [num1, num2]:
        subjects_electrodes[subject].append(elec1_name)
        subjects_electrodes[subject].append(elec2_name)
    subjects = list(subjects_electrodes.keys())
    bad_subjects = []
    for subject in subjects:
        atlas = utils.fix_atlas_name(subject, atlas, SUBJECTS_DIR)
        if not utils.both_hemi_files_exist(op.join(SUBJECTS_DIR, subject, 'label', '{}.{}.annot'.format('{hemi}', atlas))):
            anat.create_annotation(subject, atlas, annotation_template)
            if not utils.both_hemi_files_exist(
                    op.join(SUBJECTS_DIR, subject, 'label', '{}.{}.annot'.format('{hemi}', atlas))):
                print('No atlas for {}!'.format(atlas))
                bad_subjects.append((subject, 'No atlas'))
                continue
        try:
            ela_morph_electrodes.calc_elas(
                subject, subject_to, subjects_electrodes[subject], bipolar=False, atlas=atlas,overwrite=overwrite)
        except:
            err = utils.print_last_error_line()
            bad_subjects.append((subject, err))
            continue

    print(bad_subjects)


def read_morphed_electrodes(xls_fname, subject_to='colin27', bipolar=True, prefix='', postfix=''):
    output_fname = '{}electrodes{}_positions.npz'.format(prefix, '_bipolar' if bipolar else '', postfix)
    electrodes_colors = defaultdict(list)
    bad_electrodes = []
    template_electrodes = defaultdict(list)
    morphed_electrodes_fname = op.join(MMVT_DIR, subject_to, 'electrodes', 'morphed_electrodes.pkl')
    if op.isfile(morphed_electrodes_fname):
        template_electrodes, electrodes_colors = utils.load(morphed_electrodes_fname)
    else:
        for line in utils.xlsx_reader(xls_fname, skip_rows=1):
            subject, _, elec_name, _, anat_group = line
            subject = subject.replace('\'', '')
            if subject == '':
                break
            elec_group, num1, num2 = utils.elec_group_number(elec_name, bipolar)
            if '{}{}-{}'.format(elec_group, num2, num1) != elec_name:
                num1, num2 = str(num1).zfill(2), str(num2).zfill(2)
            if '{}{}-{}'.format(elec_group, num2, num1) != elec_name:
                raise Exception('Wrong group or numbers!')

            elecs_pos = []
            for num in num1, num2:
                elec_input_fname = op.join(MMVT_DIR, subject, 'electrodes', '{}{}_ela_morphed.npz'.format(elec_group, num))
                if not op.isfile(elec_input_fname):
                    print('{} not found!'.format(elec_input_fname))
                    bad_electrodes.append('{}_{}{}'.format(subject, elec_group, num))
                else:
                    d = np.load(elec_input_fname)
                    elecs_pos.append(d['pos'])
            num1, num2 = (num1, num2 )if num2 > num1 else (num2, num1)
            if len(elecs_pos) == 2:
                bipolar_ele_pos = np.mean(elecs_pos, axis=0)
                elec_name = '{}_{}{}-{}'.format(subject, elec_group, num1, num2)
                template_electrodes[subject].append((elec_name, bipolar_ele_pos))
                electrodes_colors[subject].append((elec_name, int(anat_group)))
        utils.save((template_electrodes, electrodes_colors), morphed_electrodes_fname)

    write_electrode_colors(subject_to, electrodes_colors)
    fol = utils.make_dir(op.join(MMVT_DIR, subject_to, 'electrodes'))
    output_fname = op.join(fol, output_fname)
    elecs_coordinates = np.array(utils.flat_list_of_lists(
        [[e[1] for e in template_electrodes[subject]] for subject in template_electrodes.keys()]))
    elecs_names = utils.flat_list_of_lists(
        [[e[0] for e in template_electrodes[subject]] for subject in template_electrodes.keys()])
    print('Saving {} electrodes in {}:'.format(subject_to, output_fname))
    print(elecs_names)
    np.savez(output_fname, pos=elecs_coordinates, names=elecs_names, pos_org=[])

    print('Bad electrodes:')
    print(bad_electrodes)

    return template_electrodes, electrodes_colors


# def morph_csv():
#     electrodes = morph_electrodes_to_template.read_all_electrodes(subjects, False)
#     template_electrodes = morph_electrodes_to_template.read_morphed_electrodes(
#         electrodes, template_system, SUBJECTS_DIR, MMVT_DIR, True, subjects_electrodes, convert_to_bipolar=bipolar)
#     morph_electrodes_to_template.save_template_electrodes_to_temelectrodes_csv_to_npy(subject, ras_fileplate(
#         template_electrodes, bipolar, MMVT_DIR, template_system))
#     morph_electrodes_to_template.export_into_csv(template_system, MMVT_DIR, bipolar)
#     morph_electrodes_to_template.create_mmvt_coloring_file(template_system, template_electrodes, electrodes_colors)


def write_electrode_colors(template, electrodes_colors):
    import csv
    fol = utils.make_dir(op.join(MMVT_DIR, template, 'coloring'))
    csv_fname = op.join(fol, 'morphed_electrodes.csv')
    # unique_colors = np.unique(utils.flat_list(([[k[1] for k in elecs] for elecs in electrodes_colors.values()])))
    # colors = utils.get_distinct_colors(len(unique_colors))
    from src.mmvt_addon import colors_utils as cu
    colors = [cu.name_to_rgb(c) for c in ['blue', 'green', 'purple', 'red', 'brown', 'yellow']]
    print('Writing csv file to {}'.format(csv_fname))
    with open(csv_fname, 'w') as csv_file:
        wr = csv.writer(csv_file, quoting=csv.QUOTE_NONE)
        for subject in electrodes_colors.keys():
            # for elc_name, _ in template_electrodes[subject]:
            for elc_name, color_id in electrodes_colors[subject]:
                color = colors[color_id - 1]
                wr.writerow([elc_name, *color])


if __name__ == '__main__':
    fols = ['/home/npeled/Documents/Angelique/mapping_to_common_brains',
            '/autofs/space/thibault_001/users/npeled/Documents/Angelique/mapping_to_common_brains']
    fol = [f for f in fols if op.isdir(f)][0]
    xls_fname = op.join(fol, 'ChannelListFull.xls')
    bipolar = True
    to_subject = 'colin27'
    atlas = 'laus125'
    annotation_template = 'fsaverage5c'
    overwrite = True

    read_xls(xls_fname, to_subject, atlas, annotation_template, overwrite=overwrite)
    # subjects_electrodes, electrodes_colors = read_morphed_electrodes(xls_fname, subject_to='colin27')
    # morph_electrodes_to_template.export_into_csv(subjects_electrodes, template_system, MMVT_DIR, bipolar)
    # morph_electrodes_to_template.create_mmvt_coloring_file(template_system, subjects_electrodes, electrodes_colors)
