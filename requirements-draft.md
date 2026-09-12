# Climate Justice for Nepal Web Page

## Key Idea 
Key idea is to develop a dynamic web page for awareness about the recent climate catastrophy in nepal caused due to flash flood. The website should make people aware of nepal's very low carbon footprint and yet the country has the highest impact. 

Additionally, the site would include some stats of emissions, nepal's contributions, in addition live death tools and missing number people including damages 

## AI Roles 
As a web page design and implementation, you would plan, design and implement this web site with provided instructions 

#### Key considerations 
- the whole idea is to gather user's or viewere sentiment and make them feel the climate unjustice happening to nepal. So the website should instantly caught viewer attention , spark  interest in numbers and motivate them to support in any ways mentioned below from their end 


#### Technical / design Requirements 
- very reponsive and fast to load
- minimal and clean design 
- modern look 
- Not too much text but clean theme with emotional connection 
- use latest UI technologies and libraries 
- minimal and maintainable codebase for easier extension or scale 


## Content 
Strictly note, following contents are ideas, you can be slightly creative and polish the content to make it look better. But do not make up facts or numbers. 

### Core focus

This should be a single page web page
page should feature this video /videos/aerial-video1.mp4 without any sound as cinmeograph in a sound. You can add any appropriate styling and it shlould loop. in the right button , add a small text - credit associated press 

horizontal header should have link to click different section of page 

the main catchy label 
Did you know Nepal has `0.35%` of population and only has contributed cummulated  of `0.01%` of total emissions - Source https://ourworldindata.org/profile/co2/nepal . these number should be pop as count-up animation.


In addition, another pop up number stats
Total death 
Total missing 
Home affected 
Last updated time 
Damages in total 

Now it's your job to figure out from where to get this information , scrap or API call, how to cache 


#### Context details 
Here more details about climate injustice to nepal - , take this UN post for some details https://news.un.org/en/story/2026/09/1168281  Also add section for some photos carousel for the incident. 


### Next Section 
This should be the section to ask for help. Provide some options. Following are options but add more details not just only link

- Donate directly to official government relief fund - https://donate.gov.np/ 
- Red cross - https://donate.redcrossredcrescent.org/np/default/~my-donation 
- Unicef - https://www.unicef.org/emergencies/nepal-flood 

In addition, you can also raise awareness about global warming 




In bottom, add a small section about this site is maintained volunterily . No sponsered or anything. For any further info about this site please reach out to me . Add option for instagram, facebook, linkedin, email 


Updates 
#### Carousel 
Update the carousel with single card auto sliding carousel with text overlay 
I will put pictures list under images/carousel
There would be a json file with following structure 
```
  {
    "overlay_text": "",
    "source": "",
    "source link": "",
    "image": "",
    "image_caption": "Kathmandu, Nepal, Tuesday, Sept. 1, 2026. (AP Photo/Niranjan Shrestha)"
  },

``` 

Your job is to add these images in carousel with respect to 
- overlay text should be bold highly visible, the text should convey impactful message e.g. `1/10 people from here never have flown in the Airplane ` , also add the source
-  image caption should be small caption below to credit the image author and add the context