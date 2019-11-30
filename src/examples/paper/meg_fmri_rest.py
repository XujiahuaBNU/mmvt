import os.path as op
import os
import glob
import numpy as np
from src.utils import utils
from src.utils import labels_utils as lu
from src.preproc import anatomy as anat
from src.preproc import meg
from src.preproc import fMRI as fmri
from src.preproc import connectivity
from src.utils import freesurfer_utils as fu

LINKS_DIR = utils.get_links_dir()
SUBJECTS_DIR = utils.get_link_dir(LINKS_DIR, 'subjects', 'SUBJECTS_DIR')
os.environ['SUBJECTS_DIR'] = SUBJECTS_DIR
MEG_DIR = utils.get_link_dir(LINKS_DIR, 'meg')
FMRI_DIR = utils.get_link_dir(utils.get_links_dir(), 'fMRI')
MMVT_DIR = utils.get_link_dir(LINKS_DIR, 'mmvt')


def init_anatomy(args):
    args = anat.read_cmd_args(dict(
        subject=args.subject,
        remote_subject_dir=args.remote_subject_dir,
        exclude='create_new_subject_blend_file',
        ignore_missing=True
    ))
    anat.call_main(args)


def init_meg(subject):
    utils.make_dir(op.join(MEG_DIR, subject))
    utils.make_link(op.join(args.remote_subject_dir.format(subject=subject), 'bem'),
                    op.join(MEG_DIR, subject, 'bem'))
    utils.make_link(op.join(MEG_DIR, subject, 'bem'), op.join(SUBJECTS_DIR, subject, 'bem'))


def get_meg_empty_fnames(subject, remote_fol, args, ask_for_different_day_empty=False):
    csv_fname = op.join(remote_fol, 'cfg.txt')
    if not op.isfile(csv_fname):
        print('No cfg file ({})!'.format(csv_fname))
        return '', '', ''
    day, empty_fname, cor_fname, local_rest_raw_fname = '', '', '', ''
    for line in utils.csv_file_reader(csv_fname, ' '):
        if line[4].lower() == 'resting':
            day = line[2]
            remote_rest_raw_fname = op.join(remote_fol, line[0].zfill(3), line[-1])
            if not op.isfile(remote_rest_raw_fname):
                raise Exception('rest file does not exist! {}'.format(remote_rest_raw_fname))
            local_rest_raw_fname = op.join(MEG_DIR, subject, '{}_resting_raw.fif'.format(subject))
            if not op.isfile(local_rest_raw_fname):
                utils.make_link(remote_rest_raw_fname, local_rest_raw_fname)
            break
    if day == '':
        print('Couldn\'t find the resting day in the cfg!')
        return '', '', ''
    for line in utils.csv_file_reader(csv_fname, ' '):
        if line[4] == 'empty':
            empty_fname = op.join(MEG_DIR, subject, '{}_empty_raw.fif'.format(subject))
            if op.isfile(empty_fname):
                continue
            if line[2] == day:
                remote_empty_fname = op.join(remote_fol, line[0].zfill(3), line[-1])
                if not op.isfile(remote_empty_fname):
                    raise Exception('empty file does not exist! {}'.format(remote_empty_fname))
                utils.make_link(remote_empty_fname, empty_fname)
    if not op.isfile(empty_fname):
        for line in utils.csv_file_reader(csv_fname, ' '):
            if line[4] == 'empty':
                ret = input('empty recordings from a different day were found, continue (y/n)? ') \
                        if ask_for_different_day_empty else True
                if au.is_true(ret):
                    remote_empty_fname = op.join(remote_fol, line[0].zfill(3), line[-1])
                    if not op.isfile(remote_empty_fname):
                        raise Exception('empty file does not exist! {}'.format(remote_empty_fname))
                    utils.make_link(remote_empty_fname, empty_fname)
    cor_dir = op.join(args.remote_subject_dir.format(subject=subject), 'mri', 'T1-neuromag', 'sets')
    if op.isfile(op.join(cor_dir, 'COR-{}-resting.fif'.format(subject))):
        cor_fname = op.join(cor_dir, 'COR-{}-resting.fif'.format(subject))
    elif op.isfile(op.join(cor_dir, 'COR-{}-day{}.fif'.format(subject, day))):
        cor_fname = op.join(cor_dir, 'COR-{}-day{}.fif'.format(subject, day))
    return local_rest_raw_fname, empty_fname, cor_fname


def get_fMRI_rest_fol(subject, remote_root):
    remote_fol = op.join(remote_root, '{}_01'.format(subject.upper()))
    csv_fname = op.join(remote_fol, 'cfg.txt')
    if not op.isfile(csv_fname):
        print('No cfg file!')
        return '', '', ''
    num = None
    for line in utils.csv_file_reader(csv_fname, '\t'):
        if line[1].lower() == 'resting':
            num = line[0]
            break
    if num is None:
        print ('Can\'t find rest in the cfg file for {}!'.format(subject))
        return ''
    subject_folders = glob.glob(op.join(remote_root, '{}_*'.format(subject.upper())))
    for subject_fol in subject_folders:
        # rest_fols = glob.glob(op.join(subject_fol, '**', num.zfill(3)), recursive=True)
        rest_fol = op.join(subject_fol, 'resting', num.zfill(3))
        # print(rest_fol)
        # if len(rest_fols) == 1:
        #     break
        if op.isdir(rest_fol):
            return rest_fol
    return ''
    # if len(rest_fols) == 0:
    #     print('Can\'t find rest in the cfg file for {}!'.format(subject))
    #     return ''
    # return rest_fols[0]


def convert_rest_dicoms_to_mgz(subject, rest_fol, overwrite=False):
    try:
        root = utils.make_dir(op.join(FMRI_DIR, subject))
        output_fname = op.join(root, '{}_rest.mgz'.format(subject))
        if op.isfile(output_fname):
            if not overwrite:
                return output_fname
            if overwrite:
                os.remove(output_fname)
        dicom_files = glob.glob(op.join(rest_fol, 'MR*'))
        dicom_files.sort(key=op.getmtime)
        fu.mri_convert(dicom_files[0], output_fname)
        if op.isfile(output_fname):
            return output_fname
        else:
            print('Can\'t find {}!'.format(output_fname))
            return ''
    except:
        utils.print_last_error_line()
        return ''


# def analyze_meg(args):
#     subjects = args.subject
#     for subject, mri_subject in zip(subjects, args.mri_subject):
#         init_meg(subject)
#         local_rest_raw_fname, empty_fname, cor_fname = get_meg_empty_fnames(
#             subject, args.remote_meg_dir.format(subject=subject.upper()), args)
#         if not op.isfile(empty_fname) or not op.isfile(cor_fname):
#             print('{}: Can\'t find empty, raw, or cor files!'.format(subject))
#             continue
#         args = meg.read_cmd_args(dict(
#             subject=subject,
#             mri_subject=mri_subject,
#             atlas=args.atlas,
#             function='rest_functions',
#             task='rest',
#             reject=True, # Should be True here, unless you are dealling with bad data...
#             remove_power_line_noise=True,
#             l_freq=3, h_freq=80,
#             windows_length=500,
#             windows_shift=100,
#             inverse_method='MNE',
#             raw_fname=local_rest_raw_fname,
#             cor_fname=cor_fname,
#             empty_fname=empty_fname,
#             remote_subject_dir=args.remote_subject_dir,
#             # This properties are set automatically if task=='rest'
#             # calc_epochs_from_raw=True,
#             # single_trial_stc=True,
#             # use_empty_room_for_noise_cov=True,
#             # windows_num=10,
#             # baseline_min=0,
#             # baseline_max=0,
#         ))
#         meg.call_main(args)


# def calc_meg_connectivity(args):
#     args = connectivity.read_cmd_args(utils.Bag(
#         subject=args.subject,
#         atlas='laus125',
#         function='calc_lables_connectivity',
#         connectivity_modality='meg',
#         connectivity_method='pli',
#         windows_num=1,
#         # windows_length=500,
#         # windows_shift=100,
#         recalc_connectivity=True,
#         n_jobs=args.n_jobs
#     ))
#     connectivity.call_main(args)


def calc_meg_connectivity(args):
    inv_method, em = 'dSPM', 'mean_flip'
    con_method, con_mode = 'pli2_unbiased', 'multitaper'
    subjects = args.subject
    good_subjects = []

    for subject, mri_subject in zip(subjects, args.mri_subject):
        init_meg(subject)
        local_rest_raw_fname, empty_fname, cor_fname = get_meg_empty_fnames(
            subject, op.join(args.remote_meg_dir, subject), args) # subject.upper()
        if not op.isfile(empty_fname) and not args.ignore:
            print('{}: Can\'t find empty! ({})'.format(subject, empty_fname))
            continue
        if not op.isfile(cor_fname) and not args.ignore:
            print('{}: Can\'t find cor! ({})'.format(subject, cor_fname))
            continue
        if not op.isfile(local_rest_raw_fname) and not args.ignore:
            print('{}: Can\'t find raw! ({})'.format(subject, local_rest_raw_fname))
            continue

        output_fname = op.join(MMVT_DIR, subject, 'connectivity', 'rest_{}_{}_{}.npz'.format(em, con_method, con_mode))
        if op.isfile(output_fname) and not args.ignore:
            file_mod_time = utils.file_modification_time_struct(output_fname)
            if file_mod_time.tm_year >= 2018 and (file_mod_time.tm_mon == 11 and file_mod_time.tm_mday >= 15) or \
                    (file_mod_time.tm_mon > 11):
                print('{} already exist!'.format(output_fname))
                good_subjects.append(subject)
                continue

        remote_epo_fname = op.join(args.remote_epochs_dir, subject, args.epo_template.format(subject=subject))
        if not op.isfile(remote_epo_fname) and not args.ignore:
            print('No epochs file! {}'.format(remote_epo_fname))
            continue
        con_args = meg.read_cmd_args(utils.Bag(
            subject=subject, mri_subject=subject,
            task='rest', inverse_method=inv_method, extract_mode=em, atlas=args.atlas,
            # meg_dir=args.meg_dir,
            remote_subject_dir=args.remote_subject_dir,  # Needed for finding COR
            get_task_defaults=False,
            data_per_task=False,
            fname_format=args.epo_template.format(subject=subject)[:-len('-epo.fif')],
            epo_fname=remote_epo_fname,
            raw_fname=local_rest_raw_fname,
            empty_fname=empty_fname,
            function='make_forward_solution,calc_inverse_operator,calc_labels_connectivity',
            con_method=con_method,
            con_mode=con_mode,
            conditions='rest',
            max_epochs_num=args.max_epochs_num,
            # recreate_src_spacing='oct6p',
            check_for_channels_inconsistency=False,
            overwrite_inv=True,
            overwrite_connectivity=True,#args.overwrite_connectivity,
            cor_fname=cor_fname,
            use_empty_room_for_noise_cov=True,
            n_jobs=args.n_jobs
        ))
        ret = meg.call_main(con_args)
        if ret[subject]['calc_labels_connectivity']:
            good_subjects.append(subject)
        else:
            print('Problem with {}!'.format(subject))

    print('{}/{} subjects with results:'.format(len(good_subjects), len(subjects)))
    print(good_subjects)


def analyze_rest_fmri(gargs):
    good_subjects = []
    for subject in gargs.mri_subject:
        # remote_rest_fol = get_fMRI_rest_fol(subject, gargs.remote_fmri_dir)
        # print('{}: {}'.format(subject, remote_rest_fol))
        # if remote_rest_fol == '':
        #     continue
        # local_rest_fname = convert_rest_dicoms_to_mgz(subject, remote_rest_fol, overwrite=True)
        # if local_rest_fname == '':
        #     continue
        # if not op.isfile(local_rest_fname):
        #     print('{}: Can\'t find {}!'.format(subject, local_rest_fname))
        #     continue
        # args = fmri.read_cmd_args(dict(
        #     subject=subject,
        #     atlas=gargs.atlas,
        #     remote_subject_dir=gargs.remote_subject_dir,
        #     function='clean_4d_data',
        #     fmri_file_template=local_rest_fname,
        #     overwrite_4d_preproc=True
        # ))
        # flags = fmri.call_main(args)
        # if subject not in flags or not flags[subject]['clean_4d_data']:
        #     continue


        output_fname = op.join(MMVT_DIR, subject, 'connectivity', 'fmri_corr.npz')
        if op.isfile(output_fname):
            print('{} already exist!'.format(output_fname))
            good_subjects.append(subject)
            continue
        remote_fname = op.join(
            gargs.remote_fmri_rest_dir, subject, 'rest_001', '001',
            'fmcpr.siemens.sm6.{}.{}.nii.gz'.format(subject, '{hemi}'))
        if not utils.both_hemi_files_exist(remote_fname):
            print('Couldn\t find fMRI rest data for {} ({})'.format(subject, remote_fname))
            continue
        local_fmri_fol = utils.make_dir(op.join(FMRI_DIR, subject))
        local_fmri_template = op.join(local_fmri_fol, utils.namebase_with_ext(remote_fname))
        if utils.both_hemi_files_exist(local_fmri_template):
            print('{} al')
        for hemi in utils.HEMIS:
            local_fmri_fname = op.join(local_fmri_fol, local_fmri_template.format(hemi=hemi))
            if op.isfile(local_fmri_fname):
                os.remove(local_fmri_fname)
            utils.make_link(remote_fname.format(hemi=hemi), local_fmri_fname)

        args = fmri.read_cmd_args(dict(
            subject=subject,
            atlas=gargs.atlas,
            function='analyze_4d_data',
            fmri_file_template=local_fmri_template,
            labels_extract_mode='mean',
            overwrite_labels_data=True
        ))
        flags = fmri.call_main(args)
        if subject not in flags or not flags[subject]['analyze_4d_data']:
            continue

        args = connectivity.read_cmd_args(dict(
            subject=subject,
            atlas=gargs.atlas,
            function='calc_lables_connectivity',
            connectivity_modality='fmri',
            connectivity_method='corr',
            labels_extract_mode='mean',
            windows_length=34,  # tr = 3 -> 100s
            windows_shift=4,  # 12s
            save_mmvt_connectivity=True,
            calc_subs_connectivity=False,
            recalc_connectivity=True,
            n_jobs=gargs.n_jobs
        ))
        flags = connectivity.call_main(args)
        if subject in flags and flags[subject]['calc_lables_connectivity']:
            good_subjects.append(subject)

    print('{}/{} good subjects'.format(len(good_subjects), len(gargs.mri_subject)))
    print('Good subject: ', good_subjects)
    print('Bad subjects: ', set(gargs.mri_subject) - set(good_subjects))


def merge_meg_connectivity(args):
    inv_method, em = 'dSPM', 'mean_flip'
    con_method, con_mode = 'pli2_unbiased', 'multitaper'
    bands = dict(theta=[4, 8], alpha=[8, 15], beta=[15, 30], gamma=[30, 55], high_gamma=[65, 200])
    threshold_perc = 90

    template_con = utils.make_dir(op.join(MMVT_DIR, args.template_brain, 'connectivity'))
    output_fname = op.join(template_con, 'rest_{}_{}_{}.npz'.format(em, con_method, con_mode))
    static_output_fname = op.join(template_con, 'meg_rest_{}_{}_{}_{}_mean.npz'.format(
        em, con_method, con_mode, '{band}'))
    if op.isfile(output_fname) and not args.overwrite:
        print('Averaged connectivity already exist')
        return True
    org_tempalte_labels = lu.read_labels(args.template_brain, SUBJECTS_DIR, args.atlas)
    tempalte_labels = [l for l in org_tempalte_labels if lu.get_label_hemi_invariant_name(l) not in args.labels_exclude]
    include_indices = [ind for ind, l in enumerate(org_tempalte_labels) if
                       lu.get_label_hemi_invariant_name(l) not in args.labels_exclude]
    all_con = None
    subjects_num = 0
    good_subjects = []
    for subject in args.subject:
        meg_con_fname = op.join(MMVT_DIR, subject, 'connectivity', 'rest_{}_{}_{}.npz'.format(em, con_method, con_mode))
        if not op.isfile(meg_con_fname):
            continue
        con_dict = utils.Bag(np.load(meg_con_fname))
        # print('{}: con.shape {}'.format(subject, con_dict.con.shape))
        if con_dict.con.shape[0] != len(org_tempalte_labels):
            print('Wrong number of cortical labels!')
            continue
        subject_con = con_dict.con[np.ix_(include_indices, include_indices)]
        if subject_con.shape[0] != len(tempalte_labels) or subject_con.shape[1] != len(tempalte_labels):
            print('Wrong number of cortical labels!')
            continue
        # print(np.min(subject_con), np.max(subject_con))
        if np.isnan(np.max(subject_con)):
            print('nan in data!')
            continue
        if all_con is None:
            all_con = np.zeros(subject_con.shape)
        for l in range(subject_con.shape[2]):
            subject_con[:, :, l] = sym_mat(subject_con[:, :, l])
        all_con += subject_con
        subjects_num += 1
        good_subjects.append(subject)
    all_con /= subjects_num
    np.savez(output_fname, con=all_con, names=[l.name for l in tempalte_labels])
    for band_ind, band in enumerate(bands.keys()):
        threshold = np.percentile(all_con[:, :, band_ind], threshold_perc)
        np.savez(static_output_fname.format(band=band), con=all_con[:, :, band_ind], threshold=threshold,
                 labels=[l.name for l in tempalte_labels])
    print('Good subjects: {}'.format(good_subjects))


def merge_fmri_connectivity(args):
    con_method = 'corr'
    threshold_perc = 90

    template_con = utils.make_dir(op.join(MMVT_DIR, args.template_brain, 'connectivity'))
    output_fname = op.join(template_con, 'rest_{}.npz'.format(con_method))
    output_mean_fname = op.join(template_con, 'rest_{}_mean.npz'.format(con_method))
    if op.isfile(output_fname) and not args.overwrite:
        print('Averaged connectivity already exist')
        return True
    tempalte_labels = lu.read_labels(args.template_brain, SUBJECTS_DIR, args.atlas)
    tempalte_labels = [l for l in tempalte_labels if lu.get_label_hemi_invariant_name(l) not in args.labels_exclude]
    all_con = None
    subjects_num = 0
    good_subjects = []
    for subject in args.subject:
        fmri_con_fname = op.join(MMVT_DIR, subject, 'connectivity', 'fmri_{}.npy'.format(con_method))
        if not op.isfile(fmri_con_fname):
            print('{} is missing!'.format(fmri_con_fname))
            continue
        subject_con = np.load(fmri_con_fname)
        print('{}: con.shape {}'.format(subject, subject_con.shape))
        if subject_con.shape[0] != len(tempalte_labels):
            print('Wrong number of cortical labels!')
            continue
        print(np.min(subject_con), np.max(subject_con))
        if all_con is None:
            all_con = np.zeros(subject_con.shape)
        all_con += subject_con
        subjects_num += 1
        good_subjects.append(subject)
    all_con /= subjects_num
    for w in all_con.shape[2]:
        all_con[:, :, w] = sym_mat(all_con[:, :, w])

    np.savez(output_fname, con=all_con, names=[l.name for l in tempalte_labels])
    threshold = np.percentile(all_con, threshold_perc)
    np.savez(output_mean_fname, con=all_con.mean(axis=2), threshold=threshold,
             labels=[l.name for l in tempalte_labels])
    print('Good subjects: {}'.format(good_subjects))


def merge_modalities_connectivity(args):
    inv_method, em = 'dSPM', 'mean_flip'
    meg_con_method, meg_con_mode = 'pli2_unbiased', 'multitaper'
    fmri_con_method = 'corr'
    conditions = ['interference', 'neutral']
    threshold_perc = 90

    template_con = utils.make_dir(op.join(MMVT_DIR, args.template_brain, 'connectivity'))
    # meg_con_fname = op.join(template_con, 'rest_{}_{}_{}.npz'.format(em, meg_con_method, meg_con_mode))
    meg_con_fname = op.join(template_con, 'meg_rest_{}_{}_{}_high_gamma_mean.npz'.format(em, meg_con_method, meg_con_mode))
    input_fmri_fname = op.join(template_con, 'rest_{}.npz'.format(fmri_con_method))

    conn_args = connectivity.read_cmd_args(dict(subject=args.template_brain, atlas=args.atlas, norm_by_percentile=False))
    meg_con_dict = utils.Bag(np.load(meg_con_fname))
    # meg_con = meg_con_dict.con[:, :, 4].squeeze()
    meg_con = meg_con_dict.con
    fmri_con_dict = utils.Bag(np.load(input_fmri_fname))
    fmri_con = np.abs(fmri_con_dict.con.mean(axis=2)).squeeze()
    # check_hubs_intersections(meg_con_dict, fmri_con_dict, meg_con_dict.names, threshold_perc=threshold_perc)
    print(np.min(meg_con), np.max(meg_con))
    print(np.min(fmri_con), np.max(fmri_con))
    if not all(meg_con_dict.labels == fmri_con_dict.names):
        raise Exception('Not the same names!')

    meg_con = sym_mat(meg_con)
    fmri_con = sym_mat(fmri_con)

    labels_names = meg_con_dict.labels
    meg_threshold, fmri_threshold = np.percentile(meg_con, threshold_perc), np.percentile(fmri_con, threshold_perc)
    print('meg and fMRI thresholds: {}, {}'.format(meg_threshold, fmri_threshold))
    meg_con = meg_con / (np.max(meg_con) * 2) + 0.5
    fmri_con = fmri_con / (np.max(fmri_con) * 2) + 0.5
    meg_threshold, fmri_threshold = np.percentile(meg_con, threshold_perc), np.percentile(fmri_con, threshold_perc)
    meg_hub, fmri_hub = calc_hubs(meg_con, fmri_con, labels_names, meg_threshold, fmri_threshold)
    meg_con_hubs, fmri_con_hubs, join_con_hubs = create_con_with_only_hubs(
        meg_con, fmri_con, meg_hub, fmri_hub, meg_threshold, fmri_threshold)
    for con_hubs, con_name in zip([meg_con_hubs, fmri_con_hubs, join_con_hubs], ['meg-hubs', 'fmri-hubs', 'fmri-meg-hubs']):
        output_fname = op.join(MMVT_DIR, args.template_brain, 'connectivity', '{}.npz'.format(con_name))
        con_vertices_fname = op.join(MMVT_DIR, args.template_brain, 'connectivity', '{}_vertices.pkl'.format(con_name))
        connectivity.save_connectivity(
            args.template_brain, con_hubs, args.atlas, con_name, connectivity.ROIS_TYPE, labels_names, conditions,
            output_fname, con_vertices_fname, conn_args.windows, conn_args.stat, conn_args.norm_by_percentile,
            conn_args.norm_percs, conn_args.threshold, conn_args.threshold_percentile, conn_args.symetric_colors)
        print('{} was saved in {}'.format(con_name, output_fname))


def check_hubs_intersections(meg_con_dict, fmri_con_dict, labels_names, threshold_perc=90):
    bands = dict(theta=[4, 8], alpha=[8, 15], beta=[15, 30], gamma=[30, 55], high_gamma=[65, 200])
    fmri_con = np.abs(fmri_con_dict.con.mean(axis=2)).squeeze()
    fmri_con = sym_mat(fmri_con)
    fmri_threshold = np.percentile(fmri_con, threshold_perc)
    for band_ind, band_name in enumerate(bands.keys()):
        print('******* {} ************'.format(band_name))
        meg_con = meg_con_dict.con[:, :, band_ind].squeeze()
        meg_con = sym_mat(meg_con)
        meg_threshold = np.percentile(meg_con, threshold_perc)
        calc_hubs(meg_con, fmri_con, labels_names, meg_threshold, fmri_threshold)


def sym_mat(con):
    if not np.allclose(con, con.T):
        con = (con + con.T) / 2
    return con


# def calc_con(con, top_k):
#     top_k = utils.top_n_indexes(con, top_k)
#     norm_con = np.zeros(con.shape)
#     for top in top_k:
#         norm_con[top] = con[top]
#     norm_con /= np.max(norm_con)
#     return norm_con, top_k


def calc_hubs(con_meg, con_fmri, labels, meg_threshold=0, fmri_threshold=0, topk_meg_hubs=10, topk_fmri_hubs=10):
    meg_sum = np.sum(np.abs(con_meg) > meg_threshold, 0)
    fmri_sum = np.sum(np.abs(con_fmri) > fmri_threshold, 0)
    meg_hub = np.argmax(meg_sum)
    fmri_hub = np.argmax(fmri_sum)
    top_meg_hubs = [l[:-len('_1-rh')] for l in labels[np.argsort(meg_sum)[-topk_meg_hubs:]][::-1]]
    top_fmri_hubs = [l[:-len('_1-rh')] for l in labels[np.argsort(fmri_sum)[-topk_fmri_hubs:]][::-1]]

    print('meg: {}({}) {}, fmri: {}({}) {}'.format(
        labels[meg_hub], meg_hub, np.max(meg_sum),
        labels[fmri_hub], fmri_hub, np.max(fmri_sum)))
    print('Top {} MEG hubs: {}'.format(topk_meg_hubs, top_meg_hubs))
    print('Top {} fMRI hubs: {}'.format(topk_fmri_hubs, top_fmri_hubs))
    print('Intersections: {}'.format(set(top_meg_hubs).intersection(set(top_fmri_hubs))))
    return meg_hub, fmri_hub


def create_con_with_only_hubs(con_meg, con_fmri, meg_hub, fmri_hub, meg_threshold=0, fmri_threshold=0,
                              meg_topk=15, fmri_topk=15):
    shp = con_meg.shape
    con_join_hubs, con_meg_hubs, con_fmri_hubs, clean_con_meg, clean_con_fmri = \
        np.zeros(shp), np.zeros(shp), np.zeros(shp), np.zeros(shp), np.zeros(shp)

    clean_con_meg[np.where(abs(con_meg) > meg_threshold)] = con_meg[np.where(abs(con_meg) > meg_threshold)]
    clean_con_fmri[np.where(abs(con_fmri) > fmri_threshold)] = con_fmri[np.where(abs(con_fmri) > fmri_threshold)]
    meg_topk_inds = clean_con_meg[meg_hub].argsort()[-meg_topk:]
    fmri_topk_inds = clean_con_fmri[fmri_hub].argsort()[-fmri_topk:]

    con_meg_hubs[meg_hub, meg_topk_inds] = con_meg_hubs[meg_topk_inds, meg_hub] = -con_meg[meg_hub, meg_topk_inds]
    con_fmri_hubs[fmri_hub, fmri_topk_inds] = con_fmri_hubs[fmri_topk_inds, fmri_hub] = con_fmri[fmri_hub, fmri_topk_inds]

    con_join_hubs[meg_hub, meg_topk_inds] = con_join_hubs[meg_topk_inds, meg_hub] = \
        -clean_con_meg[meg_hub, meg_topk_inds]
    con_join_hubs[fmri_hub, fmri_topk_inds] = con_join_hubs[fmri_topk_inds, fmri_hub] = \
        clean_con_fmri[fmri_hub, fmri_topk_inds]

    return con_meg_hubs, con_fmri_hubs, con_join_hubs


if __name__ == '__main__':
    import argparse
    from src.utils import args_utils as au
    from src.utils import preproc_utils as pu

    remote_epochs_dir = [d for d in [
        '/autofs/space/karima_002/users/Resting/epochs', op.join(MMVT_DIR, 'meg')] if op.isdir(d)][0]
    remote_subject_dir = [op.join(d, '{subject}') for d in [
        '/autofs/space/lilli_001/users/DARPA-Recons', SUBJECTS_DIR] if op.isdir(d)][0]

    parser = argparse.ArgumentParser(description='MMVT')
    parser.add_argument('-s', '--subject', help='subject name', required=True, type=au.str_arr_type)
    parser.add_argument('-m', '--mri_subject', help='subject name', required=False, default='')
    parser.add_argument('-a', '--atlas', required=False, default='laus125')
    parser.add_argument('-f', '--function', help='function name', required=True)
    parser.add_argument('--top_k', required=False, default=0, type=int)
    parser.add_argument('--remote_meg_dir', required=False,
                        default='/autofs/space/lilli_003/users/DARPA-TRANSFER/meg')
    parser.add_argument('--remote_epochs_dir', required=False,default=remote_epochs_dir)
    parser.add_argument('--remote_fmri_dir', required=False,
                        default='/autofs/space/lilli_003/users/DARPA-TRANSFER/mri')
    parser.add_argument('--remote_fmri_rest_dir', required=False,
                        default='/autofs/space/lilli_003/users/DARPA-RestingState/')
    parser.add_argument('--remote_subject_dir', required=False,
                        default='/autofs/space/lilli_001/users/DARPA-Recons/{subject}')
    parser.add_argument('--epo_template', required=False, default='{subject}_Resting_meg_Demi_ar-epo.fif')
    parser.add_argument('--max_epochs_num', help='', required=False, default=10, type=int)
    parser.add_argument('--template_brain', required=False, default='colin27')
    parser.add_argument('--labels_exclude', help='rois to exclude', required=False, default='unknown,corpuscallosum',
                        type=au.str_arr_type)

    parser.add_argument('--overwrite', required=False, default=False, type=au.is_true)
    parser.add_argument('--ignore', required=False, default=False, type=au.is_true)
    parser.add_argument('--n_jobs', help='cpu num', required=False, default=-1)
    args = utils.Bag(au.parse_parser(parser))
    args.subject = pu.decode_subjects(args.subject, remote_subject_dir=args.remote_subject_dir)
    if args.mri_subject == '':
        args.mri_subject = args.subject
    if args.subject[0] == 'goods':
        meg_goods = 'hc006,hc032,hc025,hc010,hc022,hc020,hc023,hc027,hc019,hc012,hc033,hc035,hc011,hc026,hc005,hc002,hc008,hc015,hc024,hc021,hc030,hc001,hc028,hc034,hc036,hc013,hc017,hc014,hc016'
        fmri_goods = 'hc036,hc002,hc022,hc014,hc042,hc035,hc015,hc033,hc045,hc011,hc010,hc005,hc006,hc041,hc019,hc009,hc047,hc034,hc028,hc031,hc026,hc024,hc044,hc013,hc030,hc021,hc008,hc029,hc018,hc032,hc038,hc012,hc025,hc037,hc007,hc001,hc017,hc023,hc020,hc003,hc016'
        args.subject = args.mri_subject = list(set(meg_goods.split(',')).intersection(set(fmri_goods.split(','))))
        print('{} good subjects in fMRI and MEG'.format(len(args.subject)))
    locals()[args.function](args)


    # MEG good subject:
    #
    # fMRI good subjects:
    # 'hc036,hc002,hc022,hc014,hc042,hc035,hc015,hc033,hc045,hc011,hc010,hc005,hc006,hc041,hc019,hc009,hc047,hc034,hc028,hc031,hc026,hc024,hc044,hc013,hc030,hc021,hc008,hc029,hc018,hc032,hc038,hc012,hc025,hc037,hc007,hc001,hc017,hc023,hc020,hc003,hc016'
