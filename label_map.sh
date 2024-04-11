#!/bin/bash

filename=$1; shift      # probability_maps/temp/combined_clusters
output_folder=$1; shift # probability_maps/temp
colorfile=$1; shift     # probability_maps/temp/colormapfile.csv
wbcommand=$1; shift     # wb_command

labelfile=${filename}.dlabel.nii
scalarfile=${filename}.dscalar.nii

echo "name,shortname,ix,n,rgb" >> ${output_folder}/combined_parcel.csv
touch ${output_folder}/combined_labelfile.txt # Added by Greg on 2020-11-06 to fix bug
for mapsystem in `cat ${colorfile}`
do
	systemfile=`echo $mapsystem | awk -F, '{print $1}'`
	system=`echo $mapsystem | awk -F, '{print $2}'`
	rgbvalues=`echo $mapsystem | awk -F, '{print $3 " " $4 " " $5 " " $6}'`
	rgbvaluesparcel=`echo $mapsystem | awk -F, '{print $3 "," $4 "," $5 "," $6}'`
	${wbcommand} -cifti-math 'x * (mask > 0)' temp_${system}.dscalar.nii -var x ${filename}.dscalar.nii -var mask ${systemfile}
	${wbcommand} -cifti-label-import temp_${system}.dscalar.nii '' temp_${system}.dlabel.nii
	${wbcommand} -cifti-label-export-table temp_${system}.dlabel.nii 1 temp_${system}_label.txt
	echo `cat temp_${system}_label.txt | grep LABEL`
	rm temp_${system}.dlabel.nii 
	labelcollate='['
	unique_count=0
	total_count=0
	duplicate_flag=false
	touch ${output_folder}/${system}_labelfile.txt
	for label in `cat temp_${system}_label.txt | grep LABEL`
	do
		# added by Greg and Feczko on 2020-11-17 to ensure label files have the right color
		echo ${system}_$label >> ${output_folder}/${system}_labelfile.txt
		labelnum=`echo $label | awk -F_ '{ print $2 }'`
		echo $labelnum $rgbvalues >> ${output_folder}/${system}_labelfile.txt
		total_count=$((total_count+1))

		# added by Greg on 2020-11-10 to prevent duplicates being added to label file
        if [[ ! "`cat combined_labelfile.txt | grep ${label}$`" = "" ]]; then  # added the last '$' on 2021-09-14 to fix a bug where the condition would conflate LABEL_1 with LABEL_11, LABEL_12, etc
			echo "Skipping duplicate label ${label} for ${system} system."
			duplicate_flag=true
		else
			echo -n "No ${system} ${label} duplicates, "
			echo ${system}_$label >> ${output_folder}/combined_labelfile.txt
			labelnum=`echo $label | awk -F_ '{ print $2 }'`
			if [[ $unique_count == 1 ]]; then labelcollate=${labelcollate}' '${labelnum}; else labelcollate=${labelcollate}','${labelnum}; fi
			echo $labelnum $rgbvalues >> ${output_folder}/combined_labelfile.txt
			unique_count=$((unique_count+1))
		fi
	done
	if $duplicate_flag; then                
		echo "Making overlap file ${system}_overlapping.dlabel.nii"
		${wbcommand} -cifti-label-import temp_${system}.dscalar.nii ${output_folder}/${system}_labelfile.txt ${system}.dlabel.nii
	else
		${wbcommand} -cifti-label-import temp_${system}.dscalar.nii ${output_folder}/${system}_labelfile.txt ${system}.dlabel.nii
	fi
	rm temp_${system}.dscalar.nii
	rm temp_${system}_label.txt     
	labelcollate=${labelcollate}']'
	echo ${system}','${system}','${labelcollate}','${unique_count}',['${rgbvaluesparcel}']' >> ${output_folder}/combined_parcel.csv
done
here=`dirname $0`
# python3 -c "import sys; sys.path.insert(1, '$here'); from probability_map_wrapper import validate_label_file; validate_label_file('${output_folder}', 'combined_labelfile.txt', 'combined_parcel.csv');"  # Added by Greg Conan 2020-06-22 to remove duplicates
${wbcommand} -cifti-label-import ${filename}.dscalar.nii ${output_folder}/combined_labelfile.txt ${filename}.dlabel.nii
