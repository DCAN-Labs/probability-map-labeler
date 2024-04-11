#!/bin/bash

threshold=$1 ;shift           # -0.75
probability_folder=$1 ;shift  # probability_maps/GRP1_singlenet/
output_folder=$1 ;shift       # probability_maps/temp
temp_folder=$1 ;shift         # probability_maps/temp
wb_command=$1 ;shift          # wb_command
min_surf_area=$1 ;shift       # 200
min_vol_area=$1 ;shift        # -200
left_midthick_file=$1 ;shift  # ABCD/average_surfaces/data/L.midthickness.surf.gii
right_midthick_file=$1 ;shift # ABCD/average_surfaces/data/R.midthickness.surf.gii

threshold=${threshold:-0.75}
wb_command=${wb_command:-'wb_command'}
min_surf_area=${min_surf_area:-200}
min_vol_area=${min_vol_area:-200}
new_command=` echo -cifti-math '"'`
count=1
for files in `ls $probability_folder`
do
	filepath=${probability_folder}/${files}
	systemname=`echo $files | awk -F.dscalar.nii '{print $1}'`
	threshfile=${temp_folder}/${systemname}_thresh.dscalar.nii
	maskedfile=${temp_folder}/${systemname}_at_${threshold}.dscalar.nii
	${wb_command} -cifti-math 'x > '${threshold}'' ${threshfile} -var x ${filepath}
	${wb_command} -cifti-math 'x*y' ${maskedfile} -var x ${threshfile} -var y ${filepath}
	if [[ $count == 1 ]]; then new_command=`echo $new_command x${count}`; else new_command=`echo $new_command +x${count}`; fi
	var_segment=`echo $var_segment -var x${count} ${maskedfile}`
	count=$(($count + 1))
done
new_command=`echo ${new_command}'"'`
full_command=`echo ${wb_command} ' ' ${new_command} ${output_folder}/combined.dscalar.nii ${var_segment}`
echo ${full_command} >> ${temp_folder}/command.txt
bash ${temp_folder}/command.txt
${wb_command} -cifti-find-clusters ${output_folder}/combined.dscalar.nii ${threshold} ${min_surf_area} ${threshold} ${min_vol_area} COLUMN ${output_folder}/combined_clusters.dscalar.nii -left-surface ${left_midthick_file} -right-surface ${right_midthick_file}
${wb_command} -cifti-label-import ${output_folder}/combined_clusters.dscalar.nii '' ${output_folder}/combined_clusters.dlabel.nii

