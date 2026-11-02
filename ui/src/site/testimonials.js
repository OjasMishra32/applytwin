// What students said after using ApplyTwin, in their own words, shown on the home page. Everyone here agreed to be
// featured. To add one: put a square photo in ./people/ (and the school's icon in ./schools/) and add an entry (order = order on the page).
import anthony from './people/anthony-du.jpg'
import hudson from './people/hudson-shields.jpg'
import nicolas from './people/nicolas-rebolloso.jpg'
import raunak from './people/raunak-mondal.jpg'
import shreyas from './people/shreyas-suman.jpg'
import siya from './people/siya-rozani.jpg'
import srijan from './people/srijan-kumbam.jpg'
import cmu from './schools/cmu.edu.png'
import scu from './schools/scu.edu.png'
import spjimr from './schools/spjimr.org.png'
import stanford from './schools/stanford.edu.png'
import uf from './schools/ufl.edu.png'

export const TESTIMONIALS = [
  { name: 'Hudson Shields', school: 'University of Florida', short: 'UF', logo: uf, photo: hudson, url: 'https://www.linkedin.com/in/hudson-shields-1590a5333/',
    quote: 'ApplyTwin is actually so tuff. Way better than anything out there. Already did 300 internships.' },
  { name: 'Nicolas Rebolloso', school: 'University of Florida', short: 'UF', logo: uf, photo: nicolas, url: 'https://www.linkedin.com/in/nicolas-rebolloso/',
    quote: 'ApplyTwin is really a lifesaver. Something like this for free is genuinely baffling. The results speak for themselves!' },
  { name: 'Srijan Kumbam', school: 'University of Florida', short: 'UF', logo: uf, photo: srijan, url: 'https://www.linkedin.com/in/srijankumbam/',
    quote: "I actually didn't expect it to work so well. Simplify is shi in comparison." },
  { name: 'Anthony Du', school: 'Stanford University', short: 'Stanford', logo: stanford, photo: anthony, url: 'https://www.linkedin.com/in/anthonypdu/',
    quote: "It's tuff. Lowkey was using Claude agents to automate my applications, but yours does it way better." },
  { name: 'Shreyas Suman', school: 'Santa Clara University', short: 'Santa Clara', logo: scu, photo: shreyas, url: 'https://www.linkedin.com/in/shreyas-suman-ba9691355/',
    quote: "I applied to 25 places. I like it a lot. Like deadass, I'd pay for this." },
  { name: 'Raunak Mondal', school: 'Carnegie Mellon University', short: 'Carnegie Mellon', logo: cmu, photo: raunak, url: 'https://www.linkedin.com/in/raunakmondal1/',
    quote: 'Lol ts is genuinely insane. Where was this when I needed it earlier?' },
  { name: 'Siya Rozani', school: 'SP Jain Institute of Management & Research', short: 'SP Jain', logo: spjimr, photo: siya, url: 'https://www.linkedin.com/in/siya-rozani-9889592a1/',
    quote: 'The platform is super helpful!' },
]
