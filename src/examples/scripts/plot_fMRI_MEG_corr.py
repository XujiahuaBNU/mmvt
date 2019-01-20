import os.path as op
import numpy as np
import bpy


# hc034
def run(mmvt):
    mu = mmvt.utils

    # Appearance
    mmvt.appearance.show_inflated()
    mmvt.show_hide.hide_hemi('rh')
    mmvt.show_hide.show_hemi('lh')

    # Plot MEG
    mmvt.coloring.clear_colors()
    mmvt.coloring.set_meg_files('dSPM_mean_flip_vertices_power_spectrum_stat')
    mmvt.coloring.set_lower_threshold(1.8)
    mmvt.coloring.color_meg_peak()
    mmvt.colorbar.set_colorbar_max_min(2.15, 1.8)
    mmvt.colorbar.set_colormap('RdOrYl')

    # Plot fMRI left superiorfrontal contours
    mmvt.labels.color_contours(
        specific_hemi='lh', filter='superiorfrontal', specific_colors=[0, 0, 1], atlas='MSIT_I-C', move_cursor=False)

    # Add data
    input_fname = op.join(mu.get_user_fol(), 'meg', 'labels_data_MSIT_power_spectrum_stat_lh.npz')
    if not op.isfile(input_fname):
        print('No data file! {}'.format(input_fname))
    d = mu.Bag(np.load(input_fname))
    mmvt.data.add_data_pool('meg_power_spectrum_stat', d.data, d.conditions)
    bpy.data.objects['meg_power_spectrum_stat'].select = True
    mmvt.selection.fit_selection()
    mmvt.coloring.set_current_time(269)